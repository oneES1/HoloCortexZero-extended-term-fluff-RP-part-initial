# Matrix adapter capability baseline

This document records the current `holo_cortex_zero.adapters.matrix` behavior before SDK replacement.

## Files

- `config.py`: Matrix runtime configuration schema.
- `adapter.py`: raw Matrix Client API adapter implementation.
- `routers.py`: static info/health routes only.
- `README.md`: human-facing adapter notes.

## Configuration Fields

`HOMESERVER_URL`

- Used by `MatrixAdapter._homeserver_url()`.
- Passed to `httpx.AsyncClient(base_url=...)`.
- Must point to a Matrix Client API homeserver. It is not tied to local HCZ deployment.

`BOT_USER_ID`

- Used by `_bot_user_id()`.
- Used for Matrix login identifier.
- Used as self user id in `get_self_info()`.
- Used to skip self messages and detect mentions in group rooms.

`BOT_PASSWORD`

- Used only when `BOT_ACCESS_TOKEN` is empty.
- Passed to raw `POST /_matrix/client/v3/login`.

`BOT_ACCESS_TOKEN`

- Preferred over password login.
- If non-empty, `init()` assigns `_access_token` directly and does not use `DEVICE_ID`.

`DEVICE_ID`

- Used only by `_login_with_password()`.
- Sent as `device_id` in raw Matrix password login.
- Does not provide E2EE support in the current adapter.

`OWNER_MATRIX_USER_ID`

- Returned by `get_primary_advanced_platform_user_ids()`.
- Shared adapter identity mapper converts this platform id to core `ADVANCED_USER_ID`.
- The adapter does not decide the HCZ advanced id.

`AUTO_JOIN_PRIVATE_INVITE`

- Used by `_handle_invites()`.
- If an invite is classified as private and this is false, the adapter does not join.

`AUTO_JOIN_GROUP_INVITE`

- Used by `_handle_invites()`.
- If an invite is classified as group and this is false, the adapter does not join.

`SYNC_TIMEOUT_MS`

- Used by `_sync_loop()` as long-poll timeout for raw `/sync`.

`STARTUP_SYNC_TIMEOUT_MS`

- Used by `_bootstrap_next_batch()` to establish `next_batch` without replaying old timeline as normal processing.

`REQUEST_TIMEOUT_SECONDS`

- Used by `httpx.Timeout(...)`.

`STATE_FILE`

- Used by `_state_path()`.
- Stores `room_map` mapping HCZ channel id to Matrix room id.

`LOG_RAW_EVENT_SUMMARY`

- Used by `_handle_timeline_event()` to log event summary only.

## Runtime State

`_client`

- `httpx.AsyncClient`.
- Owns raw HTTP requests.

`_sync_task`

- Background task running `_sync_loop()`.

`_access_token`

- Matrix bearer token, either from config or password login.

`_next_batch`

- Raw `/sync` pagination token.

`_room_map`

- Dict of `channel_id -> room_id`.
- Used by `forward_message()` to map HCZ chat_key back to Matrix room id.
- For owner private rooms, `_remember_room_route()` also stores `private_<ADVANCED_USER_ID> -> room_id`.

`_processed_event_ids`

- In-memory duplicate guard for raw timeline event ids.
- Trimmed from 1000 to 500 ids.

## Inbound Flow

`init()`

1. Creates `httpx.AsyncClient`.
2. Loads room map.
3. Uses configured access token or password login.
4. Calls `_bootstrap_next_batch()`.
5. Starts `_sync_loop()`.

`_bootstrap_next_batch()`

1. Calls raw `GET /_matrix/client/v3/sync`.
2. Saves `next_batch`.
3. Learns joined rooms into `_room_map`.
4. Saves room map.

`_sync_loop()`

1. Calls raw `/sync` with timeout and `since`.
2. Updates `_next_batch`.
3. Passes response to `_handle_sync_response()`.
4. On failure, logs warning and sleeps 5 seconds.

`_handle_sync_response()`

1. Handles invites.
2. Iterates joined room timeline events.
3. Classifies each room.
4. Remembers room route.
5. Sends each raw event to `_handle_timeline_event()`.

`_handle_invites()`

1. Reads `rooms.invite`.
2. Classifies invite as private via `_invite_looks_private()`.
3. Applies `AUTO_JOIN_PRIVATE_INVITE` or `AUTO_JOIN_GROUP_INVITE`.
4. Rejects encrypted invites if `m.room.encryption` is present.
5. Joins accepted rooms with raw `POST /rooms/{room_id}/join`.

`_handle_timeline_event()`

1. Drops duplicate/empty event ids.
2. Drops `m.room.encrypted`.
3. Drops `m.room.encryption`.
4. Accepts only `m.room.message`.
5. Drops bot self messages.
6. Builds HCZ segments via `_build_message_segments()`.
7. Updates room map.
8. Builds `PlatformUser`, `PlatformChannel`, `PlatformMessage`.
9. Sets `PlatformMessageExt.native_voice` for native Matrix voice messages.
10. Calls shared `collect_message(...)`.

## Channel and Room Mapping

`_room_hash(room_id)`

- `sha256(room_id)[:16]`.

`_channel_id_for_room(room_id, chat_type)`

- Private: `private_<room_hash>`.
- Group: `group_<room_hash>`.

`_classify_room(...)`

- Uses `/sync` summary member counts.
- Existing private mapping forces private.
- `0 < total_members <= 2` is private; otherwise group.

`_remember_room_route(...)`

- Always stores raw route channel id.
- Stores canonical advanced private channel id only when route is private and sender is owner Matrix user.

## Inbound Segment Support

`m.text`

- Strips Matrix reply fallback.
- Emits `ChatMessageSegment(TEXT)`.

`m.image`

- Downloads `mxc://` URL.
- Applies HCZ attachment policy.
- Emits `ChatMessageSegmentImage`.

`m.file`, `m.audio`, `m.video`

- Downloads `mxc://` URL.
- Applies HCZ attachment policy.
- Emits `ChatMessageSegmentFile`.

Encrypted media `content.file`

- Current raw adapter logs unsupported and does not process.

References

- `_extract_reply_event_id()` reads `m.relates_to.m.in_reply_to.event_id`.
- First tries DB lookup by Matrix event id and chat_key.
- Falls back to raw room event fetch.

Native voice

- `_is_voice_message()` requires `msgtype == m.audio` and one of:
  - `org.matrix.msc3245.voice`
  - `org.matrix.msc1767.audio`
  - `io.element.voice_message`
- `collect_message(..., trigger_agent=is_voice_message)` is still gated by shared collector identity rules.

## Trigger and Mention Behavior

`_is_tome_matrix(...)`

- Private rooms always true.
- Group rooms match:
  - full bot Matrix id in body,
  - `@<bot_localpart>` in body,
  - bot persona display name in body.
- Does not currently parse `m.mentions`.

## Attachment Policy Boundary

`_build_message_segments(...)`

- Calls `_preview_canonical_attachment_identity()` before policy.
- Calls shared `resolve_incoming_attachment_mode(...)`.
- Matrix adapter downloads bytes, but HCZ core policy decides managed/quarantine/disabled.

## Outbound Flow

`forward_message(request)`

1. Parses `request.chat_key` to channel id.
2. Resolves room id from `_room_map`.
3. Joins text and AT display into plain Matrix text body.
4. Sends text through raw `/send/m.room.message`.
5. Sends image/file/voice with `_send_media_segment()`.

`_send_media_segment(...)`

1. Validates local file exists and size.
2. Uploads raw media to `/_matrix/media/v3/upload`.
3. Sends unencrypted `m.image`, `m.audio`, or `m.file`.

## Unsupported Current Behavior

- E2EE room events (`m.room.encrypted`) are dropped.
- E2EE room enable events (`m.room.encryption`) are logged and ignored.
- Encrypted media payloads in `content.file` are not decrypted.
- Sending into encrypted rooms is raw unencrypted Matrix send and not valid E2EE behavior.
- Matrix reactions, edits, redactions, read receipts, typing notifications, and presence are not implemented.

## HCZ Boundaries That Must Not Change

- `collect_message(...)` remains the only inbound entry to HCZ message service.
- Shared canonical identity mapping remains outside Matrix SDK code.
- Matrix owner platform id maps to core `ADVANCED_USER_ID`; Matrix adapter does not choose the target id.
- `chat_key` format remains `matrix-private_<...>` or `matrix-group_<...>`.
- Advanced context id remains core `ADVANCED_USER_ID`.
- Normal context id remains chat_key.
- File policy remains in HCZ core.
- `/puss`, `/norm`, `/cute` remain handled by HCZ message service.
