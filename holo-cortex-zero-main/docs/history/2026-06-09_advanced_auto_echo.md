# Advanced auto echo replies

## Change
- Added system config for advanced-user auto echo replies with a runtime enable switch.
- Reused the existing system moment echo path to schedule automatic agent wakeups for the advanced context only.
- Added a small state machine for daily start/end windows, pending echo pause, user activity, and post-agent scheduling.
- Wired message processing to record advanced user activity, human-triggered agent scheduling, and agent completion.

## Runtime
- Enabled the runtime switch in the active config.
- Recreated only the main application container to load the new code and config.
- Left dependent service containers untouched.

## Verification
- Python compile checks passed for touched backend modules.
- Isolated business-state probe passed for first scheduling, pending behavior, non-advanced ignore, auto wake transition, human agent completion, and failure behavior.
- Main application container reported healthy after recreation.
