# 2026-06-05 NetEase Audio Ingest Boundary Fix

## Summary

Implemented NetEase share-link audio ingestion so that the downloaded audio is attached before the shared message collector runs. The collector no longer contains NetEase-specific logic.

## Boundary

- The collector, message service, context window, payload assembly, and trigger logic were not changed.
- NetEase handling now runs in adapter message preparation, after `PlatformMessage` is built and before `collect_message(...)` is called.
- Advanced users follow the existing attachment policy and create a managed `ChatMessageSegmentFile`.
- Normal users are blocked by the existing audio attachment policy before NetEase parsing or download.

## Changed Files

- `holo_cortex_zero/adapters/interface/collector.py`
- `holo_cortex_zero/adapters/telegram/message_processor.py`
- `holo_cortex_zero/adapters/matrix/adapter.py`
- `holo_cortex_zero/adapters/onebot_v11/matchers/message.py`
- `holo_cortex_zero/services/media_link/__init__.py`
- `holo_cortex_zero/services/media_link/netease_cloud.py`

## Verification

- Confirmed `collector.py` has zero NetEase references.
- Confirmed NetEase handling exists only in the adapter pre-collection stage and the media-link module.
- Confirmed syntax compilation for the touched Python files.
- Confirmed the NetEase share link resolves to a song id and downloads audio bytes without writing a business message or database row.
- Confirmed the business container was refreshed and reached healthy state.

## Commit

- `7c26f7e fix(media): route netease audio before collection`
