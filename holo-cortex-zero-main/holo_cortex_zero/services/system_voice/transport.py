from __future__ import annotations

from pathlib import Path
from typing import Optional

from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegment,
    PlatformSendSegmentType,
)
from holo_cortex_zero.adapters.utils import adapter_utils


async def send_voice_message(chat_key: str, audio_path: Path, *, ref_msg_id: Optional[str] = None) -> PlatformSendResponse:
    adapter = await adapter_utils.get_adapter_for_chat(chat_key)
    request = PlatformSendRequest(
        chat_key=chat_key,
        ref_msg_id=ref_msg_id,
        segments=[
            PlatformSendSegment(
                type=PlatformSendSegmentType.VOICE,
                file_path=str(audio_path),
            ),
        ],
    )
    return await adapter.forward_message(request)
