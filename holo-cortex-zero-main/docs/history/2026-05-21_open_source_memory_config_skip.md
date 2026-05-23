# Open Source Memory Config Skip

## Context

Deploy bundle smoke testing starts from the public default config. That config intentionally has no model groups until the operator fills in provider credentials.

## Finding

The memory runtime was intended to skip initialization when model config is incomplete, but the completeness check first looked up empty model group names and printed a startup traceback.

## Change

Treat empty or missing memory model group names as incomplete config before resolving the model group. This keeps first deploy startup clean while preserving the configured-model path.
