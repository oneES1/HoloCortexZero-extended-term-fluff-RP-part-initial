"""Matrix adapter implementation backed by matrix-nio."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import nio
from nio.crypto import OutgoingKeyRequest
from nio.crypto.attachments import decrypt_attachment

from holo_cortex_zero.adapters.interface.base import AdapterMetadata, BaseAdapter
from holo_cortex_zero.adapters.interface.collector import collect_message
from holo_cortex_zero.adapters.interface.identity import preview_canonical_inbound_identity
from holo_cortex_zero.adapters.interface.schemas.extra import PlatformMessageExt
from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformChannel,
    PlatformMessage,
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegmentType,
    PlatformUser,
)
from holo_cortex_zero.core import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name
from holo_cortex_zero.models.db_chat_message import DBChatMessage
from holo_cortex_zero.schemas.chat_message import (
    ChatMessageSegment,
    ChatMessageSegmentFile,
    ChatMessageSegmentImage,
    ChatMessageSegmentType,
    ChatType,
    build_reference_segment,
    extract_primary_reference_segment,
)
from holo_cortex_zero.services.file_system.policy import resolve_incoming_attachment_mode

from .config import MatrixConfig


@dataclass(frozen=True)
class MatrixRoomRoute:
    room_id: str
    channel_id: str
    channel_type: ChatType
    channel_name: str


class MatrixAdapter(BaseAdapter[MatrixConfig]):
    """Matrix adapter.

    Matrix SDK owns Matrix transport and E2EE. HCZ still owns identity mapping,
    channel/context separation, file policy, and message service entry.
    """

    def __init__(self, config_cls: type[MatrixConfig] = MatrixConfig):
        super().__init__(config_cls)
        self._client: Optional[nio.AsyncClient] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._room_map: Dict[str, str] = {}
        self._pending_join_routes: Dict[str, tuple[MatrixRoomRoute, str, int]] = {}
        self._processed_event_ids: set[str] = set()
        self._pending_megolm_events: Dict[str, nio.MegolmEvent] = {}
        self._sender_room_key_request_at: Dict[str, float] = {}
        self._verification_started_at: Dict[str, float] = {}
        self._dummy_session_sent_at: Dict[str, float] = {}
        self._stopping: bool = False

    @property
    def key(self) -> str:
        return "matrix"

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="Matrix",
            description="Matrix 入口适配器，身份统一交给 HCZ 主干映射",
            version="1.0.0",
            author="holo-cortex-zero",
            tags=["matrix", "chat", "e2ee"],
        )

    @property
    def chat_key_rules(self) -> List[str]:
        return [
            "私聊: `matrix-private_<user_or_room_hash>`",
            "群聊: `matrix-group_<room_hash>`",
        ]

    @property
    def init_in_background(self) -> bool:
        return True

    def get_adapter_router(self):
        from .routers import router

        return router

    async def init(self) -> None:
        self._stopping = False
        if not str(self.config.BOT_ACCESS_TOKEN or "").strip() and not str(self.config.BOT_PASSWORD or "").strip():
            logger.warning("Matrix BOT_ACCESS_TOKEN 和 BOT_PASSWORD 均未配置，跳过 Matrix 适配器初始化")
            return

        self._load_room_map()
        crypto_store_path = self._crypto_store_path()
        crypto_store_path.mkdir(parents=True, exist_ok=True)
        client_config = nio.AsyncClientConfig(
            encryption_enabled=True,
            store_sync_tokens=True,
            request_timeout=float(self.config.REQUEST_TIMEOUT_SECONDS),
        )
        self._client = nio.AsyncClient(
            self._homeserver_url(),
            user=self._bot_user_id(),
            device_id=self._device_id(),
            store_path=str(crypto_store_path),
            config=client_config,
            proxy=str(self.config.PROXY_URL or "").strip() or None,
        )
        self._register_callbacks()

        try:
            await self._login_sdk_client()
            self._install_cross_user_room_key_acceptance()
            await self._repair_e2ee_device_keys_if_needed()
            await self._upload_e2ee_keys_if_needed()
            await self._bootstrap_sync_token()
            self._sync_task = asyncio.create_task(self._sync_supervisor(), name="matrix-nio-sync-supervisor")
            logger.info("Matrix SDK 适配器初始化成功")
        except Exception:
            logger.exception("Matrix SDK 适配器初始化失败")
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        self._stopping = True
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.stop_sync_forever()
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task
        self._sync_task = None

        if self._client is not None:
            await self._client.close()
        self._client = None
        logger.info("Matrix SDK 适配器已清理")

    async def forward_message(self, request: PlatformSendRequest) -> PlatformSendResponse:
        try:
            self._require_client()
            _, channel_id = self.parse_chat_key(request.chat_key)
            room_id = self._room_map.get(channel_id, "")
            if not room_id:
                return PlatformSendResponse(success=False, error_message="Matrix room 映射未建立")

            event_ids: List[str] = []
            text_parts: List[str] = []
            for segment in request.segments:
                if segment.type == PlatformSendSegmentType.TEXT and str(segment.content or "").strip():
                    text_parts.append(str(segment.content or "").strip())
                elif segment.type == PlatformSendSegmentType.AT and segment.at_info:
                    text_parts.append(str(segment.at_info.nickname or segment.at_info.platform_user_id or "").strip())

            body = "\n".join(part for part in text_parts if part).strip()
            if body:
                response = await self._room_send(
                    room_id,
                    {
                        "msgtype": "m.text",
                        "body": body,
                    },
                )
                event_ids.append(response.event_id)

            for segment in request.segments:
                if segment.type not in {
                    PlatformSendSegmentType.IMAGE,
                    PlatformSendSegmentType.FILE,
                    PlatformSendSegmentType.VOICE,
                }:
                    continue
                media_event_id = await self._send_media_segment(room_id=room_id, segment=segment)
                event_ids.append(media_event_id)

            if not event_ids:
                return PlatformSendResponse(success=True, message_id="empty")

            message_id = event_ids[-1]
            logger.info(f"Matrix SDK 消息发送成功: segments={len(request.segments)} events={len(event_ids)}")
            return PlatformSendResponse(success=True, message_id=message_id)
        except Exception as exc:
            logger.error(f"Matrix SDK 消息发送失败: {exc.__class__.__name__}", exc_info=True)
            return PlatformSendResponse(success=False, error_message="Matrix SDK 消息发送失败")

    async def get_self_info(self) -> PlatformUser:
        return PlatformUser(
            platform_name=self.key,
            user_id=self._bot_user_id(),
            user_name=get_bot_persona_display_name(config),
            user_avatar="",
        )

    async def get_user_info(self, user_id: str, channel_id: str) -> PlatformUser:  # noqa: ARG002
        return PlatformUser(
            platform_name=self.key,
            user_id=user_id,
            user_name=self._matrix_display_name(user_id),
            user_avatar="",
        )

    async def get_channel_info(self, channel_id: str) -> PlatformChannel:
        channel_type = ChatType.GROUP if str(channel_id).startswith("group_") else ChatType.PRIVATE
        return PlatformChannel(
            channel_id=channel_id,
            channel_name=f"Matrix {channel_type.value}: {channel_id}",
            channel_type=channel_type,
            channel_avatar="",
        )

    def get_primary_advanced_platform_user_ids(self) -> set[str]:
        uid = self._owner_user_id()
        return {uid} if uid else set()

    def _register_callbacks(self) -> None:
        client = self._require_client()
        client.add_event_callback(
            self._on_room_message,
            (
                nio.RoomMessageText,
                nio.RoomMessageNotice,
                nio.RoomMessageEmote,
                nio.RoomMessageUnknown,
                nio.RoomMessageImage,
                nio.RoomMessageFile,
                nio.RoomMessageAudio,
                nio.RoomMessageVideo,
                nio.StickerEvent,
                nio.RoomEncryptedImage,
                nio.RoomEncryptedFile,
                nio.RoomEncryptedAudio,
                nio.RoomEncryptedVideo,
            ),
        )
        client.add_event_callback(self._on_megolm_event, nio.MegolmEvent)
        client.add_event_callback(self._on_invite_event, nio.InviteMemberEvent)
        client.add_to_device_callback(self._on_room_key_event, (nio.RoomKeyEvent, nio.ForwardedRoomKeyEvent))
        client.add_to_device_callback(
            self._on_key_verification_event,
            (
                nio.KeyVerificationStart,
                nio.KeyVerificationAccept,
                nio.KeyVerificationKey,
                nio.KeyVerificationMac,
                nio.KeyVerificationCancel,
            ),
        )
        client.add_response_callback(self._on_sync_response, nio.SyncResponse)

    async def _login_sdk_client(self) -> None:
        client = self._require_client()
        access_token = str(self.config.BOT_ACCESS_TOKEN or "").strip()
        if access_token:
            client.restore_login(self._bot_user_id(), self._device_id(), access_token)
            whoami = await client.whoami()
            if not isinstance(whoami, nio.WhoamiResponse):
                raise RuntimeError("Matrix SDK access_token whoami 验证失败")
            if str(whoami.user_id or "").strip() != self._bot_user_id():
                raise RuntimeError("Matrix SDK access_token user 不匹配")
            logger.info("Matrix SDK access_token whoami 验证成功")
            return
        if not self.config.BOT_PASSWORD:
            raise RuntimeError("Matrix BOT_ACCESS_TOKEN 和 BOT_PASSWORD 均为空")
        response = await client.login(self.config.BOT_PASSWORD, device_name="HCZ Matrix Adapter")
        if isinstance(response, nio.LoginResponse):
            if str(response.user_id or "").strip() != self._bot_user_id():
                raise RuntimeError("Matrix SDK password login user 不匹配")
            logger.info("Matrix SDK 密码登录成功")
            return
        raise RuntimeError(f"Matrix SDK 登录失败: {response.__class__.__name__}")

    async def _upload_e2ee_keys_if_needed(self) -> None:
        client = self._require_client()
        if not getattr(client, "olm", None):
            return
        if not bool(getattr(client, "should_upload_keys", False)):
            return
        response = await client.keys_upload()
        if isinstance(response, nio.KeysUploadResponse):
            logger.info("Matrix SDK E2EE device keys 已上传")
            return
        logger.warning(f"Matrix SDK E2EE device keys 上传失败: response={response.__class__.__name__}")

    async def _repair_e2ee_device_keys_if_needed(self) -> None:
        client = self._require_client()
        olm = getattr(client, "olm", None)
        if not olm:
            return
        local_keys = dict(getattr(olm.account, "identity_keys", {}) or {})
        if not local_keys:
            return
        client.users_for_key_query.add(self._bot_user_id())
        response = await client.keys_query()
        if not isinstance(response, nio.KeysQueryResponse):
            logger.warning(f"Matrix SDK E2EE device keys 查询失败: response={response.__class__.__name__}")
            return

        device_keys = response.device_keys.get(self._bot_user_id(), {}).get(self._device_id(), {})
        server_keys = device_keys.get("keys", {}) if isinstance(device_keys, dict) else {}
        curve_ok = server_keys.get(f"curve25519:{self._device_id()}") == local_keys.get("curve25519")
        ed_ok = server_keys.get(f"ed25519:{self._device_id()}") == local_keys.get("ed25519")
        if device_keys and curve_ok and ed_ok:
            return

        repair_response = await self._upload_e2ee_device_identity_keys()
        if isinstance(repair_response, nio.KeysUploadResponse):
            logger.warning("Matrix SDK E2EE device keys 已修复并重新上传")
            return
        logger.warning(f"Matrix SDK E2EE device keys 修复上传失败: response={repair_response.__class__.__name__}")

    async def _upload_e2ee_device_identity_keys(self) -> Any:
        client = self._require_client()
        olm = getattr(client, "olm", None)
        if not olm:
            return None
        device_id = self._device_id()
        user_id = self._bot_user_id()
        identity_keys = dict(getattr(olm.account, "identity_keys", {}) or {})
        device_keys = {
            "algorithms": list(getattr(olm, "_algorithms", [])),
            "device_id": device_id,
            "user_id": user_id,
            "keys": {
                f"curve25519:{device_id}": identity_keys.get("curve25519", ""),
                f"ed25519:{device_id}": identity_keys.get("ed25519", ""),
            },
        }
        device_keys["signatures"] = {user_id: {f"ed25519:{device_id}": olm.sign_json(device_keys)}}
        method, path, data = nio.Api.keys_upload(client.access_token, {"device_keys": device_keys})
        return await client._send(nio.KeysUploadResponse, method, path, data)

    def _install_cross_user_room_key_acceptance(self) -> None:
        client = self._require_client()
        olm = getattr(client, "olm", None)
        if not olm or getattr(olm, "_hcz_cross_user_forward_acceptance", False):
            return

        original_should_accept_forward = olm._should_accept_forward

        def should_accept_forward(sender: str, sender_key: str, event: nio.ForwardedRoomKeyEvent) -> bool:
            if self._is_expected_forwarded_room_key(sender=sender, sender_key=sender_key, event=event):
                return True
            return bool(original_should_accept_forward(sender, sender_key, event))

        olm._should_accept_forward = should_accept_forward
        olm._hcz_cross_user_forward_acceptance = True

    def _is_expected_forwarded_room_key(
        self,
        *,
        sender: str,
        sender_key: str,
        event: nio.ForwardedRoomKeyEvent,
    ) -> bool:
        client = self._require_client()
        session_id = str(getattr(event, "session_id", "") or "")
        if not session_id or session_id not in client.outgoing_key_requests:
            return False

        key_request = client.outgoing_key_requests[session_id]
        if (
            str(getattr(event, "algorithm", "") or "") != str(getattr(key_request, "algorithm", "") or "")
            or str(getattr(event, "room_id", "") or "") != str(getattr(key_request, "room_id", "") or "")
            or session_id != str(getattr(key_request, "session_id", "") or "")
        ):
            return False

        content = self._event_content(event)
        forwarded_sender_key = str(content.get("sender_key") or sender_key or "").strip()
        for pending_event in self._pending_megolm_events.values():
            if str(getattr(pending_event, "session_id", "") or "") != session_id:
                continue
            if str(getattr(pending_event, "room_id", "") or "") != str(getattr(event, "room_id", "") or ""):
                continue
            if str(getattr(pending_event, "sender_key", "") or "") != forwarded_sender_key:
                continue
            room = self._sdk_room(str(getattr(event, "room_id", "") or ""))
            if room is None or str(sender or "") not in getattr(room, "users", {}):
                continue
            device = client.device_store.device_from_sender_key(str(sender or ""), str(sender_key or ""))
            if device is None or not (bool(getattr(device, "verified", False)) or bool(getattr(device, "ignored", False))):
                continue
            return True
        return False

    async def _bootstrap_sync_token(self) -> None:
        client = self._require_client()
        response = await client.sync(
            timeout=0,
            sync_filter={"room": {"timeline": {"limit": 0}}},
            full_state=True,
            set_presence="online",
        )
        if not isinstance(response, nio.SyncResponse):
            raise RuntimeError(f"Matrix SDK bootstrap sync 失败: {response}")
        self._learn_sdk_rooms(prune=True)
        self._save_room_map()
        await self._converge_e2ee_state()
        logger.info(f"Matrix SDK bootstrap sync 完成: rooms={len(client.rooms)}")

    async def _sync_supervisor(self) -> None:
        logger.info("Matrix SDK sync supervisor 已启动")
        while not self._stopping:
            try:
                await self._sync_forever_once()
                if not self._stopping:
                    logger.warning("Matrix SDK sync loop stopped: reason=returned_without_exception restart_in=5s")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopping:
                    break
                logger.exception(f"Matrix SDK sync loop stopped: reason={exc.__class__.__name__} restart_in=5s")
            if not self._stopping:
                await asyncio.sleep(5)
        logger.info("Matrix SDK sync supervisor 已停止")

    async def _sync_forever_once(self) -> None:
        client = self._require_client()
        await client.sync_forever(
            timeout=max(1000, int(self.config.SYNC_TIMEOUT_MS or 30000)),
            loop_sleep_time=0,
            set_presence="online",
        )

    async def _on_sync_response(self, response: nio.SyncResponse) -> None:  # noqa: ARG002
        self._learn_sdk_rooms(prune=True)
        self._save_room_map()
        await self._converge_e2ee_state()
        retried = await self._retry_pending_megolm_events()
        if retried:
            logger.info(f"Matrix SDK E2EE sync 后重试待解密消息数量={retried}")

    async def _on_invite_event(self, room: nio.MatrixRoom, event: nio.InviteMemberEvent) -> None:
        client = self._require_client()
        if str(getattr(event, "state_key", "") or "") != self._bot_user_id():
            return
        is_private_invite = self._is_private_invite_event(room=room, event=event)
        route = self._route_from_sdk_room(room, chat_type=ChatType.PRIVATE if is_private_invite else ChatType.GROUP)
        if is_private_invite and not self.config.AUTO_JOIN_PRIVATE_INVITE:
            logger.info("Matrix SDK 私聊邀请未自动加入: reason=private_invite_disabled")
            return
        if not is_private_invite and not self.config.AUTO_JOIN_GROUP_INVITE:
            logger.warning("Matrix SDK 群聊邀请未自动加入: reason=group_invite_disabled")
            return
        response = await client.join(room.room_id)
        if isinstance(response, nio.JoinResponse):
            inviter = str(getattr(room, "inviter", "") or getattr(event, "sender", "") or "")
            self._pending_join_routes[room.room_id] = (route, inviter, 2)
            self._learn_sdk_rooms(prune=True)
            self._save_room_map()
            await self._converge_e2ee_state()
            invite_kind = "私聊" if is_private_invite else "群聊"
            logger.info(f"Matrix SDK 已自动加入{invite_kind}邀请")
            return
        logger.warning(f"Matrix SDK 自动加入邀请失败: response={response.__class__.__name__}")

    async def _on_megolm_event(self, _room: nio.MatrixRoom, event: nio.MegolmEvent) -> None:
        event_id = str(getattr(event, "event_id", "") or "").strip()
        if event_id:
            self._pending_megolm_events[event_id] = event
            if len(self._pending_megolm_events) > 500:
                self._pending_megolm_events = dict(list(self._pending_megolm_events.items())[-250:])
        try:
            await self._require_client().request_room_key(event)
            logger.warning("Matrix SDK E2EE 消息缺少 room key，已请求补钥匙并缓存等待重试")
        except nio.LocalProtocolError:
            logger.info("Matrix SDK E2EE 消息缺少 room key，补钥匙请求已存在，继续缓存等待重试")
        except Exception as exc:
            logger.warning(f"Matrix SDK E2EE 补钥匙请求失败，已缓存等待后续重试: {exc.__class__.__name__}")
        sender_requested = await self._request_room_key_from_sender(event)
        if sender_requested:
            logger.warning("Matrix SDK E2EE 已向原始发送设备请求 room key")
        room_device_requests = await self._request_room_key_from_room_devices(event)
        if room_device_requests:
            logger.warning(f"Matrix SDK E2EE 已向房间设备请求 room key 数量={room_device_requests}")

    async def _request_room_key_from_sender(self, event: nio.MegolmEvent) -> bool:
        client = self._require_client()
        sender = str(getattr(event, "sender", "") or "").strip()
        sender_device = str(getattr(event, "device_id", "") or "").strip()
        session_id = str(getattr(event, "session_id", "") or "").strip()
        room_id = str(getattr(event, "room_id", "") or "").strip()
        if not sender or not session_id or not room_id:
            return False

        request_key = f"{sender}|{sender_device}|{room_id}|{session_id}"
        now = time.monotonic()
        if now - self._sender_room_key_request_at.get(request_key, 0.0) < 60.0:
            return False
        self._sender_room_key_request_at[request_key] = now

        message = event.as_key_request(
            sender,
            str(getattr(client, "device_id", "") or self._device_id()),
            device_id=sender_device or None,
        )
        if getattr(client, "olm", None):
            key_request = OutgoingKeyRequest.from_message(message)
            client.outgoing_key_requests[key_request.request_id] = key_request
            if getattr(client.olm, "store", None):
                with contextlib.suppress(Exception):
                    client.olm.store.add_outgoing_key_request(key_request)

        response = await client.to_device(message, tx_id=f"hcz-sender-room-key-{int(time.time() * 1000)}")
        return isinstance(response, nio.ToDeviceResponse)

    async def _request_room_key_from_room_devices(self, event: nio.MegolmEvent) -> int:
        client = self._require_client()
        session_id = str(getattr(event, "session_id", "") or "").strip()
        room_id = str(getattr(event, "room_id", "") or "").strip()
        if not session_id or not room_id:
            return 0
        room = self._sdk_room(room_id)
        if room is None:
            return 0
        try:
            room_devices = client.room_devices(room_id)
        except Exception:
            return 0

        sent = 0
        now = time.monotonic()
        requester_device = str(getattr(client, "device_id", "") or self._device_id())
        for user_id, user_devices in room_devices.items():
            for device_id in user_devices:
                if str(user_id or "") == self._bot_user_id() and str(device_id or "") == requester_device:
                    continue
                request_key = f"room|{user_id}|{device_id}|{room_id}|{session_id}"
                if now - self._sender_room_key_request_at.get(request_key, 0.0) < 60.0:
                    continue
                message = event.as_key_request(str(user_id), requester_device, device_id=str(device_id))
                if getattr(client, "olm", None) and session_id not in client.outgoing_key_requests:
                    key_request = OutgoingKeyRequest.from_message(message)
                    client.outgoing_key_requests[key_request.request_id] = key_request
                    if getattr(client.olm, "store", None):
                        with contextlib.suppress(Exception):
                            client.olm.store.add_outgoing_key_request(key_request)
                response = await client.to_device(message, tx_id=f"hcz-room-room-key-{int(time.time() * 1000)}-{sent}")
                if isinstance(response, nio.ToDeviceResponse):
                    self._sender_room_key_request_at[request_key] = now
                    sent += 1
        return sent

    async def _on_room_key_event(self, event: nio.RoomKeyEvent) -> None:
        retried = await self._retry_pending_megolm_events(
            room_id=str(getattr(event, "room_id", "") or ""),
            session_id=str(getattr(event, "session_id", "") or ""),
        )
        logger.info(f"Matrix SDK E2EE room key 已接收，重试待解密消息数量={retried}")

    async def _on_key_verification_event(self, event: nio.KeyVerificationEvent) -> None:
        transaction_id = str(getattr(event, "transaction_id", "") or "")
        if not transaction_id:
            return
        client = self._require_client()
        try:
            if isinstance(event, nio.KeyVerificationStart):
                await client.accept_key_verification(transaction_id)
                logger.info("Matrix SDK E2EE 设备验证请求已自动接受")
            elif isinstance(event, nio.KeyVerificationKey):
                await self._flush_to_device_messages()
                message = client.confirm_key_verification(transaction_id)
                await client.to_device(message)
                logger.info("Matrix SDK E2EE 设备验证 SAS 已自动确认")
            elif isinstance(event, nio.KeyVerificationAccept):
                await self._flush_to_device_messages()
            elif isinstance(event, nio.KeyVerificationMac):
                sas = client.key_verifications.get(transaction_id) if getattr(client, "olm", None) else None
                if sas is not None and getattr(sas, "verified", False):
                    logger.info("Matrix SDK E2EE 设备验证已完成")
            await self._flush_to_device_messages()
        except nio.LocalProtocolError as exc:
            logger.info(f"Matrix SDK E2EE 设备验证状态跳过: {exc.__class__.__name__}")
        except Exception as exc:
            logger.warning(f"Matrix SDK E2EE 设备验证处理失败: {exc.__class__.__name__}")

    async def _converge_e2ee_state(self) -> None:
        client = self._require_client()
        if not getattr(client, "olm", None):
            return
        await self._upload_e2ee_keys_if_needed()
        with contextlib.suppress(Exception):
            if bool(getattr(client, "should_query_keys", False)):
                await client.keys_query()
        trusted = self._trust_room_devices()
        if trusted:
            logger.info(f"Matrix SDK E2EE 已信任房间设备数量={trusted}")
        await self._claim_missing_olm_sessions()
        dummy_sent = self._queue_room_device_dummy_messages()
        if dummy_sent:
            logger.info(f"Matrix SDK E2EE 已发送 Olm dummy 消息数量={dummy_sent}")
        started = await self._start_room_device_verifications()
        if started:
            logger.info(f"Matrix SDK E2EE 已发起设备验证数量={started}")
        await self._flush_to_device_messages()

    def _trust_room_devices(self) -> int:
        client = self._require_client()
        trusted = 0
        for room in client.rooms.values():
            if not bool(getattr(room, "encrypted", False)):
                continue
            try:
                room_devices = client.room_devices(room.room_id)
            except Exception:
                continue
            for user_devices in room_devices.values():
                for device in user_devices.values():
                    if str(getattr(device, "id", "") or "") == self._device_id():
                        continue
                    if bool(getattr(device, "verified", False)):
                        continue
                    if client.verify_device(device):
                        trusted += 1
        return trusted

    async def _claim_missing_olm_sessions(self) -> None:
        client = self._require_client()
        for room in client.rooms.values():
            if not bool(getattr(room, "encrypted", False)):
                continue
            try:
                missing_sessions = client.get_missing_sessions(room.room_id)
            except Exception:
                continue
            if not missing_sessions:
                continue
            with contextlib.suppress(Exception):
                await client.keys_claim(missing_sessions)

    def _queue_room_device_dummy_messages(self) -> int:
        client = self._require_client()
        olm = getattr(client, "olm", None)
        if not olm:
            return 0
        now = time.monotonic()
        queued = 0
        for room in client.rooms.values():
            if not bool(getattr(room, "encrypted", False)):
                continue
            try:
                room_devices = client.room_devices(room.room_id)
            except Exception:
                continue
            for user_id, user_devices in room_devices.items():
                for device_id, device in user_devices.items():
                    if str(device_id or "") == self._device_id():
                        continue
                    key = f"{user_id}|{device_id}"
                    if now - self._dummy_session_sent_at.get(key, 0.0) < 3600.0:
                        continue
                    session = olm.session_store.get(getattr(device, "curve25519", ""))
                    if session is None:
                        continue
                    try:
                        olm._queue_dummy_message(session, device)
                    except Exception:
                        continue
                    self._dummy_session_sent_at[key] = now
                    queued += 1
        return queued

    async def _start_room_device_verifications(self) -> int:
        client = self._require_client()
        now = time.monotonic()
        started = 0
        for room in client.rooms.values():
            if not bool(getattr(room, "encrypted", False)):
                continue
            try:
                room_devices = client.room_devices(room.room_id)
            except Exception:
                continue
            for user_id, user_devices in room_devices.items():
                for device_id, device in user_devices.items():
                    if str(device_id or "") == self._device_id():
                        continue
                    key = f"{user_id}|{device_id}"
                    if now - self._verification_started_at.get(key, 0.0) < 3600.0:
                        continue
                    if client.get_active_sas(str(user_id), str(device_id)) is not None:
                        continue
                    try:
                        await client.start_key_verification(device)
                    except Exception:
                        continue
                    self._verification_started_at[key] = now
                    started += 1
        return started

    async def _flush_to_device_messages(self) -> None:
        client = self._require_client()
        with contextlib.suppress(Exception):
            await client.send_to_device_messages()

    async def _retry_pending_megolm_events(self, *, room_id: str = "", session_id: str = "") -> int:
        if not self._pending_megolm_events:
            return 0
        client = self._require_client()
        retried = 0
        for event_id, pending_event in list(self._pending_megolm_events.items()):
            pending_room_id = str(getattr(pending_event, "room_id", "") or "")
            if room_id and pending_room_id != room_id:
                continue
            if session_id and str(getattr(pending_event, "session_id", "") or "") != session_id:
                continue
            room = self._sdk_room(pending_room_id)
            if room is None:
                continue
            try:
                decrypted_event = client.decrypt_event(pending_event)
            except Exception:
                continue
            if decrypted_event is None or isinstance(decrypted_event, nio.MegolmEvent):
                continue
            await self._on_room_message(room, decrypted_event)
            self._pending_megolm_events.pop(event_id, None)
            retried += 1
        return retried

    async def _on_room_message(self, room: nio.MatrixRoom, event: Any) -> None:
        event_id = str(getattr(event, "event_id", "") or "").strip()
        if not event_id or event_id in self._processed_event_ids:
            return
        self._processed_event_ids.add(event_id)
        if len(self._processed_event_ids) > 1000:
            self._processed_event_ids = set(list(self._processed_event_ids)[-500:])

        sender = str(getattr(event, "sender", "") or "")
        if sender == self._bot_user_id():
            return
        if self.config.LOG_RAW_EVENT_SUMMARY:
            logger.info(
                f"Matrix SDK event: type={event.__class__.__name__} decrypted={getattr(event, 'decrypted', False)}"
            )

        route = self._route_from_sdk_room(room)
        chat_key = f"{self.key}-{route.channel_id}"
        policy_chat_key, policy_sender_id = self._preview_canonical_attachment_identity(sender=sender, route=route)
        segments = await self._build_message_segments_from_sdk(
            room=room,
            event=event,
            chat_key=policy_chat_key,
            chat_type=route.channel_type,
            canonical_sender_id_for_policy=policy_sender_id,
        )
        if not segments:
            logger.warning(f"Matrix SDK 暂不支持消息类型或内容为空: type={event.__class__.__name__}")
            return

        text = self._extract_text_content(segments)
        before_map = dict(self._room_map)
        self._remember_room_route(route, sender=sender)
        if self._room_map != before_map:
            self._save_room_map()
            logger.info("Matrix SDK room 映射已更新")

        sender_display_name = self._matrix_sender_display_name(sender, room)
        platform_user = PlatformUser(
            platform_name=self.key,
            user_id=sender,
            user_name=sender_display_name,
            user_avatar="",
        )
        platform_channel = PlatformChannel(
            channel_id=route.channel_id,
            channel_name=route.channel_name,
            channel_type=route.channel_type,
            channel_avatar="",
        )
        platform_message = PlatformMessage(
            message_id=event_id,
            sender_id=sender,
            sender_name=sender_display_name,
            sender_nickname=sender_display_name,
            content_text=text,
            content_data=segments,
            is_tome=self._is_tome_matrix(event=event, route=route),
            is_self=False,
            ext_data=self._build_reference_ext(segments, chat_key=chat_key),
        )
        if platform_message.ext_data:
            platform_message.ext_data.native_voice = self._is_voice_message(self._event_content(event))
        await collect_message(
            self,
            platform_channel,
            platform_user,
            platform_message,
            trigger_agent=self._is_voice_message(self._event_content(event)),
        )

    async def _build_message_segments_from_sdk(
        self,
        *,
        room: nio.MatrixRoom,
        event: Any,
        chat_key: str,
        chat_type: ChatType,
        canonical_sender_id_for_policy: str,
    ) -> List[ChatMessageSegment]:
        segments: List[ChatMessageSegment] = []
        ref_segment = await self._build_reference_segment_from_event(room=room, event=event, chat_key=chat_key)
        if ref_segment is not None:
            segments.append(ref_segment)

        content = self._event_content(event)
        body = self._strip_reply_fallback(str(getattr(event, "body", "") or content.get("body") or "")).strip()
        if isinstance(event, (nio.RoomMessageText, nio.RoomMessageNotice, nio.RoomMessageEmote, nio.RoomMessageUnknown)):
            if body:
                segments.append(ChatMessageSegment(type=ChatMessageSegmentType.TEXT, text=body))
            return segments

        if not isinstance(
            event,
            (
                nio.RoomMessageImage,
                nio.RoomMessageFile,
                nio.RoomMessageAudio,
                nio.RoomMessageVideo,
                nio.StickerEvent,
                nio.RoomEncryptedImage,
                nio.RoomEncryptedFile,
                nio.RoomEncryptedAudio,
                nio.RoomEncryptedVideo,
            ),
        ):
            return segments

        media_bytes, mime_type = await self._download_event_media(event)
        if not media_bytes:
            return segments
        max_bytes = max(1, int(config.MAX_UPLOAD_SIZE_MB or 10)) * 1024 * 1024
        if len(media_bytes) > max_bytes:
            logger.warning(
                f"Matrix SDK 媒体下载后超过大小限制，已跳过落盘: bytes={len(media_bytes)} max={max_bytes}"
            )
            return segments

        mime_type = mime_type or self._event_mime_type(event) or "application/octet-stream"
        file_name = self._safe_media_filename(body=body, mime_type=mime_type, mxc_uri=str(getattr(event, "url", "") or ""), msgtype=self._event_msgtype(event))
        attachment_kind = self._attachment_kind(msgtype=self._event_msgtype(event), mime_type=mime_type)
        is_voice_message = self._is_voice_message(content)
        ingest_mode, reason = resolve_incoming_attachment_mode(
            adapter_key=self.key,
            chat_key=chat_key,
            chat_type=chat_type.value,
            sender_id=canonical_sender_id_for_policy,
            platform_userid=canonical_sender_id_for_policy,
            attachment_kind=attachment_kind,
            channel_type=chat_type.value,
        )
        logger.info(
            f"Matrix SDK 附件接收策略: kind={attachment_kind} voice={is_voice_message} "
            f"encrypted={self._is_encrypted_media_event(event)} mode={ingest_mode} "
            f"reason={reason} bytes={len(media_bytes)}"
        )
        if ingest_mode == "disabled":
            return segments
        segment_cls = ChatMessageSegmentImage if attachment_kind == "image" else ChatMessageSegmentFile
        segment = await segment_cls.create_from_bytes(
            media_bytes,
            from_chat_key=chat_key,
            file_name=file_name,
            ingest_mode=ingest_mode,
            mime_type=mime_type,
        )
        segments.append(segment)
        return segments

    async def _download_event_media(self, event: Any) -> tuple[bytes, str]:
        client = self._require_client()
        mxc_uri = str(getattr(event, "url", "") or "").strip()
        if not mxc_uri.startswith("mxc://"):
            logger.warning("Matrix SDK 媒体消息缺少 mxc url")
            return b"", ""
        response = await client.download(mxc=mxc_uri)
        if not isinstance(response, nio.MemoryDownloadResponse):
            logger.warning(f"Matrix SDK 媒体下载失败: response={response.__class__.__name__}")
            return b"", ""
        body = bytes(response.body or b"")
        if self._is_encrypted_media_event(event):
            try:
                body = decrypt_attachment(
                    body,
                    str(getattr(event, "key", {}).get("k", "") or ""),
                    str(getattr(event, "hashes", {}).get("sha256", "") or ""),
                    str(getattr(event, "iv", "") or ""),
                )
            except Exception as exc:
                logger.warning(f"Matrix SDK 加密媒体解密失败: {exc.__class__.__name__}")
                return b"", ""
        return body, str(getattr(response, "content_type", "") or "")

    async def _send_media_segment(self, *, room_id: str, segment: Any) -> str:
        client = self._require_client()
        file_path = Path(str(getattr(segment, "file_path", "") or ""))
        if not file_path.exists() or not file_path.is_file():
            raise RuntimeError("Matrix 待发送文件不存在")

        file_name = file_path.name
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        max_bytes = max(1, int(config.MAX_UPLOAD_SIZE_MB or 10)) * 1024 * 1024
        file_size = file_path.stat().st_size
        if file_size > max_bytes:
            raise RuntimeError(f"Matrix 待发送文件超过大小限制: bytes={file_size} max={max_bytes}")

        room = self._sdk_room(room_id)
        if room is None:
            raise RuntimeError("Matrix room 未同步，拒绝发送媒体")
        encrypt_media = bool(room.encrypted)
        with file_path.open("rb") as file_obj:
            upload_response, decryption_info = await client.upload(
                file_obj,
                content_type=mime_type,
                filename=file_name,
                encrypt=encrypt_media,
                filesize=file_size,
            )
        if not isinstance(upload_response, nio.UploadResponse):
            raise RuntimeError(f"Matrix media upload failed: {upload_response}")

        if segment.type == PlatformSendSegmentType.IMAGE:
            msgtype = "m.image"
        elif segment.type == PlatformSendSegmentType.VOICE:
            msgtype = "m.audio"
        else:
            msgtype = "m.file"

        content: dict[str, Any] = {
            "msgtype": msgtype,
            "body": file_name,
            "info": {
                "mimetype": mime_type,
                "size": file_size,
            },
        }
        if encrypt_media:
            file_info = dict(decryption_info or {})
            file_info["url"] = upload_response.content_uri
            content["file"] = file_info
        else:
            content["url"] = upload_response.content_uri

        response = await self._room_send(room_id, content)
        logger.info(f"Matrix SDK 媒体发送成功: msgtype={msgtype} encrypted={encrypt_media} bytes={file_size}")
        return response.event_id

    async def _room_send(self, room_id: str, content: dict[str, Any]) -> nio.RoomSendResponse:
        client = self._require_client()
        response = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
            tx_id=f"hcz-{int(time.time() * 1000)}",
            ignore_unverified_devices=bool(self.config.IGNORE_UNVERIFIED_DEVICES),
        )
        if isinstance(response, nio.RoomSendResponse):
            return response
        raise RuntimeError(f"Matrix room_send failed: {response}")

    async def _build_reference_segment_from_event(
        self,
        *,
        room: nio.MatrixRoom,
        event: Any,
        chat_key: str,
    ) -> Optional[ChatMessageSegment]:
        ref_event_id = self._extract_reply_event_id(self._event_content(event))
        if not ref_event_id:
            return None

        ref_msg = await DBChatMessage.filter(adapter_key=self.key, message_id=ref_event_id, chat_key=chat_key).order_by("-id").first()
        if ref_msg is not None:
            try:
                ref_segments = ref_msg.parse_content_data()
            except Exception as exc:
                logger.info(f"Matrix SDK 引用消息 DB 解析失败，降级为空引用: {exc.__class__.__name__}")
                ref_segments = []
            return build_reference_segment(
                ref_msg_id=ref_event_id,
                ref_chat_key=chat_key,
                ref_sender_id=str(ref_msg.sender_id or ""),
                ref_sender_name=str(ref_msg.sender_nickname or ref_msg.sender_name or ref_msg.sender_id or ""),
                ref_send_timestamp=int(ref_msg.send_timestamp or 0),
                ref_segments=ref_segments,
                max_text_len=int(getattr(config, "REFERENCE_TEXT_MAX_LEN", 120) or 120),
            )

        client = self._require_client()
        try:
            response = await client.room_get_event(room.room_id, ref_event_id)
        except Exception as exc:
            logger.info(f"Matrix SDK 引用消息拉取失败: {exc.__class__.__name__}")
            return self._empty_reference(ref_event_id=ref_event_id, chat_key=chat_key)
        if not isinstance(response, nio.RoomGetEventResponse):
            logger.info(f"Matrix SDK 引用消息拉取失败: response={response.__class__.__name__}")
            return self._empty_reference(ref_event_id=ref_event_id, chat_key=chat_key)

        ref_event = response.event
        ref_segments = self._build_reference_fallback_segments(self._event_content(ref_event))
        ref_sender = str(getattr(ref_event, "sender", "") or "")
        ref_origin_ts = self._safe_int(getattr(ref_event, "server_timestamp", 0)) // 1000
        return build_reference_segment(
            ref_msg_id=ref_event_id,
            ref_chat_key=chat_key,
            ref_sender_id=ref_sender,
            ref_sender_name=self._matrix_display_name(ref_sender),
            ref_send_timestamp=ref_origin_ts,
            ref_segments=ref_segments,
            max_text_len=int(getattr(config, "REFERENCE_TEXT_MAX_LEN", 120) or 120),
        )

    @staticmethod
    def _empty_reference(*, ref_event_id: str, chat_key: str) -> ChatMessageSegment:
        return build_reference_segment(
            ref_msg_id=ref_event_id,
            ref_chat_key=chat_key,
            ref_sender_id="",
            ref_sender_name="",
            ref_send_timestamp=0,
            ref_segments=[],
            ref_text="[引用消息正文未取回]",
            max_text_len=int(getattr(config, "REFERENCE_TEXT_MAX_LEN", 120) or 120),
        )

    @staticmethod
    def _extract_reply_event_id(content: dict[str, Any]) -> str:
        relates_to = content.get("m.relates_to", {})
        if not isinstance(relates_to, dict):
            return ""
        in_reply_to = relates_to.get("m.in_reply_to", {})
        if not isinstance(in_reply_to, dict):
            return ""
        return str(in_reply_to.get("event_id") or "").strip()

    def _build_reference_fallback_segments(self, content: dict[str, Any]) -> List[ChatMessageSegment]:
        msgtype = str(content.get("msgtype") or "")
        body = self._strip_reply_fallback(str(content.get("body") or "")).strip()
        if msgtype == "m.text":
            return [ChatMessageSegment(type=ChatMessageSegmentType.TEXT, text=body)] if body else []
        label = {
            "m.image": "[引用图片]",
            "m.audio": "[引用音频]",
            "m.video": "[引用视频]",
            "m.file": "[引用文件]",
        }.get(msgtype, "[引用消息正文未取回]")
        if body and msgtype in {"m.image", "m.audio", "m.video", "m.file"}:
            label = f"{label} {body}"
        return [ChatMessageSegment(type=ChatMessageSegmentType.TEXT, text=label)]

    def _learn_sdk_rooms(self, *, prune: bool = False) -> None:
        client = self._require_client()
        learned_map: Dict[str, str] = {}
        joined_room_ids = set(client.rooms.keys())
        for room in client.rooms.values():
            route = self._route_from_sdk_room(room)
            self._remember_room_route(route, room_map=learned_map)
            if route.channel_type == ChatType.PRIVATE and self._room_has_user(room, self._owner_user_id()):
                self._remember_room_route(route, sender=self._owner_user_id(), room_map=learned_map)
        for room_id in list(self._pending_join_routes.keys()):
            route, sender, remaining = self._pending_join_routes[room_id]
            if room_id in joined_room_ids:
                del self._pending_join_routes[room_id]
                continue
            self._remember_room_route(route, sender=sender, room_map=learned_map)
            if remaining <= 1:
                del self._pending_join_routes[room_id]
            else:
                self._pending_join_routes[room_id] = (route, sender, remaining - 1)
        if prune:
            self._room_map = learned_map
            return
        self._room_map.update(learned_map)

    @staticmethod
    def _room_hash(room_id: str) -> str:
        return hashlib.sha256(str(room_id or "").encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _channel_id_for_room(self, room_id: str, chat_type: ChatType) -> str:
        prefix = "group" if chat_type == ChatType.GROUP else "private"
        return f"{prefix}_{self._room_hash(room_id)}"

    def _route_from_sdk_room(self, room: nio.MatrixRoom, *, chat_type: Optional[ChatType] = None) -> MatrixRoomRoute:
        chat_type = chat_type or (ChatType.PRIVATE if self._is_private_sdk_room(room) else ChatType.GROUP)
        channel_id = self._channel_id_for_room(room.room_id, chat_type)
        room_name = str(getattr(room, "display_name", "") or getattr(room, "name", "") or "").strip()
        channel_name = room_name or f"Matrix {chat_type.value}: {channel_id}"
        return MatrixRoomRoute(
            room_id=room.room_id,
            channel_id=channel_id,
            channel_type=chat_type,
            channel_name=channel_name,
        )

    def _is_private_sdk_room(self, room: nio.MatrixRoom) -> bool:
        if self._room_has_name_or_alias(room):
            return False
        try:
            total_members = int(getattr(room, "member_count", 0) or 0)
        except Exception:
            total_members = 0
        if total_members > 0:
            return total_members <= 2

        users = getattr(room, "users", {})
        if isinstance(users, dict) and users:
            return len(users) <= 2

        for mapped_channel_id, mapped_room_id in self._room_map.items():
            if mapped_room_id == room.room_id and str(mapped_channel_id).startswith("private_"):
                return True
        return False

    def _is_private_invite_event(self, *, room: nio.MatrixRoom, event: nio.InviteMemberEvent) -> bool:
        content = getattr(event, "content", {})
        is_direct = bool(isinstance(content, dict) and content.get("is_direct") is True)
        if is_direct:
            return True
        inviter = str(getattr(room, "inviter", "") or getattr(event, "sender", "") or "")
        has_name_or_alias = self._room_has_name_or_alias(room)
        if self.is_primary_advanced_platform_user(inviter) and not has_name_or_alias:
            logger.info(
                f"Matrix SDK owner 邀请未携带 is_direct=true 且无 name/alias，按高级私聊邀请处理: "
                f"room_id={room.room_id} inviter={inviter}"
            )
            return True
        if has_name_or_alias:
            return False
        logger.info(
            f"Matrix SDK 邀请未携带 is_direct=true，按群聊/未知邀请处理: "
            f"room_id={room.room_id} inviter={inviter}"
        )
        return False

    def _remember_room_route(
        self,
        route: MatrixRoomRoute,
        *,
        sender: str = "",
        room_map: Optional[Dict[str, str]] = None,
    ) -> None:
        target = room_map if room_map is not None else self._room_map
        if route.channel_id:
            target[route.channel_id] = route.room_id
        if route.channel_type == ChatType.PRIVATE and self.is_primary_advanced_platform_user(sender):
            target[self.canonical_private_channel_id()] = route.room_id

    @staticmethod
    def _room_has_name_or_alias(room: nio.MatrixRoom) -> bool:
        return bool(str(getattr(room, "name", "") or getattr(room, "canonical_alias", "") or "").strip())

    @staticmethod
    def _room_has_user(room: nio.MatrixRoom, user_id: str) -> bool:
        expected = str(user_id or "").strip()
        if not expected:
            return False
        users = getattr(room, "users", {})
        if isinstance(users, dict) and expected in {str(item) for item in users.keys()}:
            return True
        invited_users = getattr(room, "invited_users", {})
        return isinstance(invited_users, dict) and expected in {str(item) for item in invited_users.keys()}

    def _preview_canonical_attachment_identity(
        self,
        *,
        sender: str,
        route: MatrixRoomRoute,
    ) -> tuple[str, str]:
        preview = preview_canonical_inbound_identity(
            adapter=self,
            raw_platform_userid=sender,
            raw_channel_id=route.channel_id,
            channel_type=route.channel_type,
        )
        return preview.canonical_chat_key, preview.canonical_userid

    def _is_tome_matrix(self, *, event: Any, route: MatrixRoomRoute) -> bool:
        if route.channel_type == ChatType.PRIVATE:
            return True
        content = self._event_content(event)
        mentions = content.get("m.mentions", {})
        if isinstance(mentions, dict):
            user_ids = mentions.get("user_ids", [])
            if isinstance(user_ids, list) and self._bot_user_id() in {str(item) for item in user_ids}:
                return True
        body = self._strip_reply_fallback(str(getattr(event, "body", "") or content.get("body") or "")).lower()
        bot_user_id = self._bot_user_id().lower()
        bot_localpart = bot_user_id.split(":", 1)[0].lstrip("@")
        persona_name = get_bot_persona_display_name(config).lower()
        if bot_user_id and bot_user_id in body:
            return True
        if bot_localpart and f"@{bot_localpart}" in body:
            return True
        return bool(persona_name and persona_name in body)

    def _matrix_sender_display_name(self, sender: str, room: nio.MatrixRoom) -> str:
        if str(sender or "").strip() == self._bot_user_id():
            return get_bot_persona_display_name(config)
        user = getattr(room, "users", {}).get(sender) if hasattr(room, "users") else None
        display = str(getattr(user, "display_name", "") or "").strip() if user is not None else ""
        return display or self._matrix_display_name(sender)

    @staticmethod
    def _strip_reply_fallback(body: str) -> str:
        text = str(body or "")
        if not text.startswith(">"):
            return text
        for sep in ("\n\n", "\r\n\r\n"):
            if sep in text:
                return text.split(sep, 1)[1]
        return text

    def _matrix_display_name(self, user_id: str) -> str:
        if str(user_id or "").strip() == self._owner_user_id():
            return str(user_id or "").strip()
        if str(user_id or "").strip() == self._bot_user_id():
            return get_bot_persona_display_name(config)
        return str(user_id or "").strip()

    @staticmethod
    def _extract_text_content(segments: List[ChatMessageSegment]) -> str:
        text_parts: List[str] = []
        for segment in segments:
            seg_type = getattr(segment, "type", None)
            seg_type_value = seg_type if isinstance(seg_type, str) else getattr(seg_type, "value", str(seg_type or ""))
            if seg_type_value == ChatMessageSegmentType.TEXT.value and str(getattr(segment, "text", "") or ""):
                text_parts.append(str(segment.text))
        return "\n".join(text_parts).strip()

    @staticmethod
    def _build_reference_ext(segments: List[ChatMessageSegment], *, chat_key: str) -> PlatformMessageExt:
        ref_segment = extract_primary_reference_segment(segments)
        if not ref_segment:
            return PlatformMessageExt()
        return PlatformMessageExt(
            ref_chat_key=ref_segment.ref_chat_key or chat_key,
            ref_msg_id=ref_segment.ref_msg_id,
            ref_sender_id=ref_segment.ref_sender_id,
        )

    @staticmethod
    def _event_content(event: Any) -> dict[str, Any]:
        source = getattr(event, "source", {})
        if not isinstance(source, dict):
            return {}
        content = source.get("content", {})
        return content if isinstance(content, dict) else {}

    @staticmethod
    def _event_msgtype(event: Any) -> str:
        content = MatrixAdapter._event_content(event)
        msgtype = str(content.get("msgtype") or "")
        if msgtype:
            return msgtype
        if isinstance(event, (nio.RoomMessageImage, nio.RoomEncryptedImage, nio.StickerEvent)):
            return "m.image"
        if isinstance(event, (nio.RoomMessageAudio, nio.RoomEncryptedAudio)):
            return "m.audio"
        if isinstance(event, nio.RoomMessageVideo):
            return "m.video"
        return "m.file"

    @staticmethod
    def _event_mime_type(event: Any) -> str:
        content = MatrixAdapter._event_content(event)
        info = content.get("info", {})
        if isinstance(info, dict):
            mime_type = str(info.get("mimetype") or "").strip()
            if mime_type:
                return mime_type
        return str(getattr(event, "mimetype", "") or "").strip()

    @staticmethod
    def _is_encrypted_media_event(event: Any) -> bool:
        return isinstance(
            event,
            (
                nio.RoomEncryptedImage,
                nio.RoomEncryptedFile,
                nio.RoomEncryptedAudio,
                nio.RoomEncryptedVideo,
            ),
        )

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    @staticmethod
    def _attachment_kind(*, msgtype: str, mime_type: str) -> str:
        normalized_mime = str(mime_type or "").lower()
        if msgtype == "m.image" or normalized_mime.startswith("image/"):
            return "image"
        if msgtype == "m.audio" or normalized_mime.startswith("audio/"):
            return "audio"
        if msgtype == "m.video" or normalized_mime.startswith("video/"):
            return "video"
        return "file"

    @staticmethod
    def _is_voice_message(content: dict[str, Any]) -> bool:
        if str(content.get("msgtype") or "") != "m.audio":
            return False
        return any(
            marker in content
            for marker in (
                "org.matrix.msc3245.voice",
                "io.element.voice_message",
            )
        )

    @staticmethod
    def _safe_media_filename(*, body: str, mime_type: str, mxc_uri: str, msgtype: str) -> str:
        raw_name = Path(str(body or "").replace("\\", "/")).name.strip()
        if raw_name and raw_name not in {".", ".."}:
            return raw_name[:160]
        media_id = MatrixAdapter._media_id_from_mxc(mxc_uri)
        suffix = mimetypes.guess_extension(mime_type or "") or {
            "m.image": ".jpg",
            "m.audio": ".ogg",
            "m.video": ".mp4",
        }.get(msgtype, ".bin")
        return f"matrix_{media_id[:48]}{suffix}"

    @staticmethod
    def _media_id_from_mxc(mxc_uri: str) -> str:
        value = str(mxc_uri or "").strip()
        if not value.startswith("mxc://"):
            return "media"
        rest = value[len("mxc://") :]
        _, _, media_id = rest.partition("/")
        return media_id or "media"

    def _sdk_room(self, room_id: str) -> Optional[nio.MatrixRoom]:
        client = self._require_client()
        return client.rooms.get(room_id)

    def _require_client(self) -> nio.AsyncClient:
        if self._client is None:
            raise RuntimeError("Matrix SDK client 未初始化")
        return self._client

    def _homeserver_url(self) -> str:
        return str(self.config.HOMESERVER_URL or "").strip().rstrip("/")

    def _bot_user_id(self) -> str:
        return str(self.config.BOT_USER_ID or "").strip()

    def _owner_user_id(self) -> str:
        return str(self.config.OWNER_MATRIX_USER_ID or "").strip()

    def _device_id(self) -> str:
        return str(self.config.DEVICE_ID or "HCZ_MATRIX_ADAPTER").strip() or "HCZ_MATRIX_ADAPTER"

    def _crypto_store_path(self) -> Path:
        configured = str(self.config.CRYPTO_STORE_PATH or "crypto_store").strip() or "crypto_store"
        path = Path(configured)
        if path.is_absolute():
            return path
        return self.config_path.parent / path

    def _state_path(self) -> Path:
        configured = str(self.config.STATE_FILE or "room_map.json").strip() or "room_map.json"
        path = Path(configured)
        if path.is_absolute():
            return path
        return self.config_path.parent / path

    def _load_room_map(self) -> None:
        path = self._state_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8") or "{}")
                room_map = data.get("room_map", data)
                if isinstance(room_map, dict):
                    self._room_map = {str(k): str(v) for k, v in room_map.items() if str(k) and str(v)}
        except Exception:
            logger.exception(f"Matrix room map 加载失败: {path}")
            self._room_map = {}

    def _save_room_map(self) -> None:
        path = self._state_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"room_map": self._room_map}, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            logger.exception(f"Matrix room map 保存失败: {path}")
