# Frontend Matrix adapter navigation fix

## Problem

Backend adapter registration contains four adapter keys:

- `onebot_v11`
- `sse`
- `telegram`
- `matrix`

The frontend static adapter config only listed three keys:

- `onebot_v11`
- `sse`
- `telegram`

As a result, Matrix existed in the backend adapter API but did not appear in the frontend adapter navigation.

## Evidence

- Backend source: `holo_cortex_zero/adapters/__init__.py`
- Frontend source before fix: `frontend/src/config/adapters.tsx`
- Missing locale keys before fix:
  - `frontend/src/locales/zh-CN/adapter.json`
  - `frontend/src/locales/en-US/adapter.json`

## Fix

Add the existing `matrix` adapter key to the frontend adapter config and reuse the existing generic adapter config page.

No new route, no new backend logic, no Matrix-specific parallel UI path.

## Verification

Run:

```bash
pnpm --dir frontend build
```

Then sync frontend build output to the running container with the existing minimal backend service recreate command.

