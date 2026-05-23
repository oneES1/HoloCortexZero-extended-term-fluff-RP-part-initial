# 2026-05-23 WebUI favicon dark logo

## Background

- User requested the website icon use `/home/ubuntu/logo_darkmode.png`
- Source image is a transparent PNG with a white mark, so the favicon needs a black background for visibility

## Changes

- Generated a new favicon asset:
  - `frontend/public/favicon-dark-512.png`
- Updated favicon reference:
  - `frontend/index.html`
  - changed from `/favicon.ico`
  - to `/favicon-dark-512.png`

## Asset generation

- Source:
  - `/home/ubuntu/logo_darkmode.png`
- Output:
  - `512x512` PNG
- Treatment:
  - centered white transparent source on a black square background

## Verification

- Ran frontend build successfully:
  - `pnpm --dir /home/ubuntu/hcz-deploy/holo-cortex-zero-main/frontend build`
- Verified built output contains:
  - `frontend/dist/favicon-dark-512.png`
- Verified built HTML references:
  - `/webui/favicon-dark-512.png`

## Impact

- Only affects the browser tab/site icon for the WebUI
- No backend, Docker, nginx, or routing changes
