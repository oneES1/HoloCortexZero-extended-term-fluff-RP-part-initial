# LLM image long-edge policy

## Change
- Moved image longest-edge normalization into the shared LLM router media policy.
- Default max long edge is 2048 for all emitter protocols.
- Added `__hcz_image_max_long_edge` as the generic override key and kept `local_chat_image_max_long_edge` as an input alias.
- Removed the local `/responses` 640px special case so images at or below 2048 are not resized.

## Verification
- Container compile check passed for the touched LLM modules.
- Container media-policy probe verified default 2048, generic override, legacy alias, and no-op behavior below the limit.
