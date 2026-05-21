# Matrix SDK replacement function-level plan

Scope: only files under `holo_cortex_zero/adapters/matrix`.

Target: replace raw HTTP Matrix transport with latest `matrix-nio[e2e]` SDK usage while preserving HCZ adapter boundary.

## Config Changes

`MatrixConfig`

- Keep existing fields:
  - `HOMESERVER_URL`
  - `BOT_USER_ID`
  - `BOT_PASSWORD`
  - `BOT_ACCESS_TOKEN`
  - `DEVICE_ID`
  - `OWNER_MATRIX_USER_ID`
  - `AUTO_JOIN_PRIVATE_INVITE`
  - `AUTO_JOIN_GROUP_INVITE`
  - `SYNC_TIMEOUT_MS`
  - `REQUEST_TIMEOUT_SECONDS`
  - `STATE_FILE`
  - `LOG_RAW_EVENT_SUMMARY`
- Remove raw-only `STARTUP_SYNC_TIMEOUT_MS`.
- Add:
  - `CRYPTO_STORE_PATH: str = "crypto_store"`
  - `IGNORE_UNVERIFIED_DEVICES: bool = False`

## Adapter State

`MatrixAdapter.__init__`

- Replace `_client: httpx.AsyncClient` with `_client: nio.AsyncClient`.
- Keep:
  - `_sync_task`
  - `_room_map`
  - `_processed_event_ids`
- Remove:
  - `_access_token`
  - `_next_batch`

## Initialization

`init()`

1. Import nio at module import time. If unavailable, adapter import fails loudly.
2. Load room map.
3. Create `AsyncClientConfig(encryption_enabled=True, store_sync_tokens=True, request_timeout=REQUEST_TIMEOUT_SECONDS)`.
4. Create `AsyncClient(homeserver, user=BOT_USER_ID, device_id=DEVICE_ID, store_path=crypto_store_path, config=client_config)`.
5. Register callbacks:
   - message media/text events -> `_on_room_message`
   - invite events -> `_on_invite_event`
   - sync responses -> `_on_sync_response`
6. Login:
   - If `BOT_ACCESS_TOKEN` exists: `restore_login(BOT_USER_ID, DEVICE_ID, BOT_ACCESS_TOKEN)`.
   - Else: `await client.login(BOT_PASSWORD, device_name="HCZ Matrix Adapter")`.
7. Start `sync_forever(...)` task.

`cleanup()`

1. Stop SDK sync.
2. Cancel task.
3. Close SDK client.

## Inbound Callbacks

`_on_sync_response(response)`

- Learn joined rooms from `client.rooms`.
- Save room map.

`_on_invite_event(room, event)`

1. Classify invite as private/group using room member count and room metadata available from SDK object.
2. Apply `AUTO_JOIN_PRIVATE_INVITE` or `AUTO_JOIN_GROUP_INVITE`.
3. Join via `client.join(room.room_id)`.

`_on_room_message(room, event)`

1. Drop self messages.
2. Deduplicate event id.
3. Convert SDK room to `MatrixRoomRoute`.
4. Convert SDK event source/content to HCZ segments.
5. Build `PlatformUser`, `PlatformChannel`, `PlatformMessage`.
6. Set `native_voice`.
7. Call `collect_message(...)`.

`_on_megolm_event(room, event)`

- Log decryption failure with room id/event id/sender.
- Do not inject empty message.

## Route and Identity Helpers

Keep function names where possible:

- `_room_hash`
- `_channel_id_for_room`
- `_remember_room_route`
- `_preview_canonical_attachment_identity`
- `_is_tome_matrix`
- `_matrix_sender_display_name`
- `_strip_reply_fallback`
- `_matrix_display_name`
- `_extract_text_content`
- `_build_reference_ext`
- `_attachment_kind`
- `_is_voice_message`
- `_safe_media_filename`

Replace:

- `_classify_room(room_id, room_payload)` -> `_route_from_sdk_room(room)`
- `_invite_looks_private(events)` -> `_is_private_sdk_room(room)`

Remove raw HTTP helpers:

- `_login_with_password`
- `_request`
- `_request_binary_json`
- `_request_binary`
- `_bootstrap_next_batch`
- `_sync_loop`
- `_handle_sync_response`
- `_handle_invites`
- `_handle_timeline_event`
- `_download_mxc`
- `_parse_mxc_uri` if SDK download accepts full mxc URI.

## Segment Conversion

`_build_message_segments_from_sdk(room, event, chat_key, chat_type, canonical_sender_id_for_policy)`

- Text:
  - Use `event.body`.
  - Strip reply fallback.
- Media:
  - Use `event.source["content"]`.
  - Read `url` or encrypted `file`.
  - Use `client.download(mxc=...)` for plain media.
  - If SDK exposes decrypted media in download for encrypted file, use it; otherwise log unsupported encrypted media.
  - Apply shared `resolve_incoming_attachment_mode(...)`.

## Outbound

`forward_message(request)`

1. Resolve room id from `_room_map`.
2. Text and AT -> `client.room_send(..., message_type="m.room.message", content={"msgtype": "m.text", "body": body}, ignore_unverified_devices=config.IGNORE_UNVERIFIED_DEVICES)`.
3. Media:
   - Upload with `client.upload(..., encrypt=room.encrypted)`.
   - Send content with `url` or encrypted `file` metadata returned by SDK.

## What Must Not Change

- No changes outside `holo_cortex_zero/adapters/matrix` in this implementation step.
- No changes to collector, identity mapper, message service, DB models, or QQ/TG.
- No changes to chat_key format.
- No changes to context selection.
- No new parallel Matrix adapter registration.

## Known Blocker Under Current Scope

The source replacement needs `nio` available at runtime. Current HCZ project dependencies do not provide it. Because the allowed edit boundary excludes dependency files, production deployment will require a later explicit dependency step outside this plan.
