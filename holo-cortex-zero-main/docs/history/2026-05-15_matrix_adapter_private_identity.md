# Matrix adapter private identity mapping

Date: 2026-05-15

## Goal

Add a Matrix adapter for the private Element entry while keeping HCZ identity management unified with the existing advanced user id.

## 2026-05-16 Update

This private-only adapter mapping has been superseded by the shared adapter identity mainline:

- Matrix adapter now declares only the platform-side owner id `OWNER_MATRIX_USER_ID`.
- HCZ canonical advanced id comes only from `ADVANCED_USER_ID`.
- Inbound identity mapping is handled by `holo_cortex_zero.adapters.interface.identity`.
- Matrix private/group channels are stored as room-backed channel ids and outbound uses the adapter room map.
- Existing `IMPERSONATE_PRIVATE_USER_ID`, `IMPERSONATE_PRIVATE_DISPLAY_NAME`, and `PRIVATE_CHANNEL_ID` config fields are retained only for old config loading and no longer decide runtime HCZ identity.

## Mainline

Matrix protocol identities are transport details only. The adapter rewrites the approved owner private chat into the canonical HCZ identity:

- Matrix owner: `@owner:example.com`
- Matrix bot: `@bot:example.com`
- HCZ user id: `<ADVANCED_USER_ID>`
- HCZ display name: `海泡菜`
- HCZ channel id: `private_<ADVANCED_USER_ID>`
- HCZ chat key: `matrix-private_<ADVANCED_USER_ID>`

The real Matrix `room_id` is persisted only in the Matrix adapter state file (`room_map.json`) and is used only for outbound Matrix API calls.

## Implementation

- Added `holo_cortex_zero.adapters.matrix`.
- Registered adapter key `matrix`.
- Used the existing adapter contract:
  - inbound: Matrix `/sync` event -> `PlatformUser` / `PlatformChannel` / `PlatformMessage` -> `collect_message(...)`
  - outbound: `PlatformSendRequest` -> Matrix `m.room.message`
- No new dependency was added; the adapter uses existing `httpx`.
- Supports owner-only unencrypted private text, image, audio, video, and file messages.

## Boundaries

- No Matrix group support.
- No Matrix E2EE support in the raw HTTP adapter. The Element private room must remain unencrypted for this adapter.
- Owner invites that already contain `m.room.encryption` are rejected instead of auto-joined.
- `m.room.encrypted` timeline events are logged and dropped explicitly.
- Inbound Matrix media uses the existing HCZ attachment ingestion policy and persists files with `from_chat_key=matrix-private_<ADVANCED_USER_ID>`.
- Outbound bot image, file, and voice segments are uploaded to the Matrix media API before sending `m.room.message`.
- Advanced private chats now trigger the normal post-processing path on accepted media segments, not only text segments. This is a general advanced-private rule, not a Matrix-only shortcut.
- Advanced mode commands are unchanged:
  - `/cute` -> deek
  - `/puss` -> deep
  - `/norm` -> norm
  - `/clear` and `/clearall` use the existing advanced-context clear path.
- No HCZ protocol shortcut is introduced; all inbound messages pass through `collect_message`.

## 2026-05-15 Element X encrypted DM repair

Observed facts:

- Element X created encrypted room `!rXerzXXMpeOYGCFfEZ:example.com`.
- Synapse recorded the owner sending `m.room.encrypted` in that room.
- The owner left that room at `2026-05-15 23:31:35 +0800`.
- The raw HTTP adapter has no `nio` / `olm` E2EE client store in the running container, so it cannot decrypt Matrix E2EE payloads.

Repair:

- Bot left the encrypted room through Matrix Client API; leave returned HTTP `200`.
- Bot created unencrypted room `!exampleRoom:example.com` and invited `@owner:example.com`.
- New room `m.room.encryption` state query returned HTTP `404`, meaning no encryption state is set.
- New room member check returned two joined members:
  - `@bot:example.com`
  - `@owner:example.com`
- Runtime state was set to:

```json
{
  "room_map": {
    "private_<ADVANCED_USER_ID>": "!exampleRoom:example.com"
  }
}
```

Next E2EE path:

- True Matrix E2EE support requires an E2EE-capable Matrix client library plus persistent Olm/Megolm key storage and device key upload.
- It cannot be implemented as a small extension of the existing raw `httpx` adapter because Synapse cannot decrypt E2EE message bodies for clients.

## Verification

Run:

```bash
python -m py_compile \
  holo_cortex_zero/adapters/__init__.py \
  holo_cortex_zero/adapters/matrix/adapter.py \
  holo_cortex_zero/adapters/matrix/config.py \
  holo_cortex_zero/adapters/matrix/routers.py
```

Runtime validation after enabling config:

```text
Element @hpc -> Matrix room -> adapter /sync -> HCZ chat_key matrix-private_<ADVANCED_USER_ID>
HCZ reply -> MatrixAdapter.forward_message -> same Matrix room
```
