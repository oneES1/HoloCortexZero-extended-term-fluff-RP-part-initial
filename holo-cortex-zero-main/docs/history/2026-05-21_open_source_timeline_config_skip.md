# Open Source Timeline Config Skip

## Context

Deploy bundle smoke testing starts with an empty `MODEL_GROUPS` map until the operator configures an LLM provider.

## Finding

Startup completed, but timeline initialization printed a traceback when `TIMELINE_MODEL_GROUP` was empty.

## Change

Timeline compression now stays disabled when the configured model group is empty or missing. This keeps first deploy startup clean and preserves the explicit configured-model path for real compression.
