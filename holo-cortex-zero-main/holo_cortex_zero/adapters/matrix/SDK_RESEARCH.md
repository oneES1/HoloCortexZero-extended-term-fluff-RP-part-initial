# Matrix SDK research

Research date: 2026-05-16.

## Sources

- Official nio documentation: https://matrix-nio.readthedocs.io/en/latest/
- Official nio examples: https://matrix-nio.readthedocs.io/en/latest/examples.html
- Official matrix-nio GitHub/PyPI metadata from search results.
- Local temporary introspection environment: `/tmp/hcz_nio_probe`.

## Package and Dependency Facts

Official docs identify `matrix-nio` as a Matrix client library with an asyncio layer. Docs list:

- transparent E2EE support,
- encrypted file uploads and downloads,
- token based login,
- live syncing,
- reactions/tags/typing/redaction support,
- no cross-signing support,
- no server-side key backup support,
- no in-room emoji verification.

Official installation facts:

- `pip install matrix-nio` installs without E2EE support.
- E2EE requires `python-olm`.
- `python-olm` requires system `libolm` C library version 3.x.
- Debian/Ubuntu package named by docs: `libolm-dev`.
- E2EE install command after libolm exists: `pip install matrix-nio[e2e]`.

Local HCZ facts:

- Repo `pyproject.toml` has no `matrix-nio`, `nio`, or `olm` dependency.
- `python3` and `uv run python` cannot import `nio` or `olm`.
- Temporary official-PyPI install in `/tmp/hcz_nio_probe` succeeded with `matrix-nio[e2e]`.
- Therefore code replacement inside `holo_cortex_zero/adapters/matrix` can be written, but production import requires dependency changes outside the allowed edit boundary.

## Verified SDK API Signatures

Introspection from installed `matrix-nio[e2e]`:

```text
AsyncClient.__init__(
    homeserver: str,
    user: str = "",
    device_id: Optional[str] = "",
    store_path: Optional[str] = "",
    config: Optional[AsyncClientConfig] = None,
    ssl: Optional[bool] = None,
    proxy: Optional[str] = None,
)
```

```text
AsyncClientConfig(
    store=DefaultStore,
    encryption_enabled=True,
    store_name="",
    pickle_key="DEFAULT_KEY",
    store_sync_tokens=False,
    custom_headers=None,
    max_limit_exceeded=None,
    max_timeouts=None,
    backoff_factor=0.1,
    max_timeout_retry_wait_time=60,
    request_timeout=60,
    io_chunk_size=65536,
)
```

```text
AsyncClient.login(password=None, device_name="", token=None)
AsyncClient.restore_login(user_id, device_id, access_token)
AsyncClient.sync_forever(timeout=None, sync_filter=None, since=None, full_state=None, loop_sleep_time=None, first_sync_filter=None, set_presence=None)
AsyncClient.room_send(room_id, message_type, content, tx_id=None, ignore_unverified_devices=False)
AsyncClient.upload(data_provider, content_type="application/octet-stream", filename=None, encrypt=False, monitor=None, filesize=None)
AsyncClient.download(mxc=None, filename=None, allow_remote=True, server_name=None, media_id=None, save_to=None)
AsyncClient.join(room_id)
AsyncClient.close()
AsyncClient.add_event_callback(callback, filter)
AsyncClient.add_response_callback(func, cb_filter=None)
AsyncClient.stop_sync_forever()
AsyncClient.room_get_event(room_id, event_id)
```

Available classes verified:

```text
AsyncClient
AsyncClientConfig
ClientConfig
LoginResponse
RoomSendResponse
UploadResponse
DownloadResponse
MemoryDownloadResponse
MatrixRoom
RoomMessageText
RoomMessageImage
RoomMessageFile
RoomMessageAudio
RoomMessageVideo
MegolmEvent
InviteEvent
InviteMemberEvent
SyncResponse
ErrorResponse
```

## Official Example Facts

Basic client example:

- Instantiate `AsyncClient(homeserver, user_id)`.
- Register `client.add_event_callback(message_callback, RoomMessageText)`.
- `await client.login(password)`.
- Send with `await client.room_send(room_id, message_type="m.room.message", content={...})`.
- Sync with `await client.sync_forever(timeout=30000)`.

Stored token example:

- Official example persists homeserver, user_id, device_id, access_token.
- Restored login can set those values or use SDK restore login API.

Encrypted example:

- Docs create a client with `store_path=STORE_FOLDER`.
- Docs use config with `store_sync_tokens=True`.
- Docs mention device trust ordering matters before full sync.

## SDK Replacement Consequences

Replaced by SDK:

- raw `httpx.AsyncClient`,
- raw `/login`,
- raw `/sync`,
- raw `/join`,
- raw `/send`,
- raw media upload/download for Matrix transport,
- raw E2EE rejection path.

Kept by HCZ adapter:

- `MatrixRoomRoute`,
- `room_id -> channel_id` mapping,
- `_room_map` storage format,
- `PlatformUser`, `PlatformChannel`, `PlatformMessage` construction,
- `collect_message(...)`,
- shared canonical identity mapping,
- shared attachment policy,
- `forward_message(PlatformSendRequest)`,
- chat_key rules.

## Boundary Conflict With Current User Constraint

The requested code boundary is `holo_cortex_zero/adapters/matrix`.

Full SDK replacement requires at least these outside-boundary runtime changes:

- project dependency: `matrix-nio[e2e]`,
- lock file update,
- likely Docker/system package dependency for `libolm-dev`,
- container rebuild.

Without those, importing `nio` in production will raise `ModuleNotFoundError`.

Therefore this document distinguishes:

- source-code replacement inside `adapters/matrix`: possible;
- runnable production replacement: blocked until dependency boundary is allowed.
