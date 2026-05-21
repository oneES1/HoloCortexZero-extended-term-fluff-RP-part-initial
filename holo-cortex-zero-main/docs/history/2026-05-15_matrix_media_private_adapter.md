# Matrix media private adapter

Date: 2026-05-15

## Goal

Extend the private Matrix adapter without introducing a second HCZ message path.

## Behavior

- Inbound Matrix `m.text` remains a text segment.
- Inbound Matrix `m.image` becomes a HCZ image segment.
- Inbound Matrix `m.audio`, `m.video`, and `m.file` become HCZ file segments.
- Matrix `mxc://` media is downloaded through the Matrix media API and then passed to the existing HCZ attachment ingestion policy.
- The Matrix owner is still rewritten to:

```text
platform_userid = <ADVANCED_USER_ID>
sender_id = <ADVANCED_USER_ID>
sender_name = 海泡菜
chat_key = matrix-private_<ADVANCED_USER_ID>
```

## Outbound

The adapter now accepts existing platform send segments:

- `TEXT` -> Matrix `m.text`
- `IMAGE` -> Matrix media upload + `m.image`
- `FILE` -> Matrix media upload + `m.file`
- `VOICE` -> Matrix media upload + `m.audio`

This allows existing `_ctx.send_image(...)`, `_ctx.send_file(...)`, and system voice transport to use Matrix.

## Trigger Rule

Existing private chat logic only triggered post-processing for text segments. Advanced user private chats now also trigger on accepted media segments:

```text
image, file, voice, video
```

This rule is generic for advanced private chats and is not Matrix-specific.

## Commands

Advanced mode commands are unchanged:

```text
/cute  -> deek
/puss  -> deep
/norm  -> norm
/clear -> clear context records
/clearall -> clear context records and compressed summaries
```

## Limits

- Matrix E2EE media is not supported.
- Matrix group rooms are not supported.
- Media size follows `MAX_UPLOAD_SIZE_MB`.
