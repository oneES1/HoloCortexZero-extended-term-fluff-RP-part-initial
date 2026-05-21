# Docker Network Cleanup

## Scope

Only two Docker network cleanup items were changed:

- Removed the hard-coded NapCat DNS servers from the main compose file.
- Removed the hard-coded `<DOCKER_BRIDGE_SUBNET>` bridge subnet and `<HOST_GATEWAY_IP>` gateway from the main compose file.

No runtime containers were restarted during this cleanup.

## Production Env

The local ignored `.env` keeps the current production container proxy entrypoint:

```env
HCZ_HTTP_PROXY=socks5h://<CONTAINER_SOCKS_PROXY>
HCZ_HTTPS_PROXY=socks5h://<CONTAINER_SOCKS_PROXY>
HCZ_ALL_PROXY=socks5h://<CONTAINER_SOCKS_PROXY>
```

This proxy points to the host `sing-box` SOCKS listener currently bound on the Docker bridge gateway.
It is intentionally not encoded in `docker-compose.yml`.

## Verification

Static checks confirmed these Docker network settings are absent from `docker-compose.yml` and `.env.share.example`:

- `dns:`
- `8.8.8.8`
- `1.1.1.1`
- `<DOCKER_BRIDGE_SUBNET_BASE>`
- `<HOST_GATEWAY_IP>`
- `ipam:`
- `subnet:`
- `gateway:`

The local ignored `.env` is allowed to keep the production proxy address because it is runtime configuration, not compose network topology.

`docker compose config` was run against both local `.env` and `.env.share.example`.
