# Tool HTTP Default Proxy

## Scope

Generic tool HTTP requests now use the framework system proxy setting instead of implicitly inheriting container proxy environment variables.

Changed path:

- `holo_cortex_zero/services/tools/host/bridge.py`

## Behavior

`HCZToolHostBridge.http_request(...)` now resolves:

```yaml
DEFAULT_PROXY
```

from the system config and passes it explicitly to `httpx.AsyncClient`.

The client is created with:

```python
trust_env=False
```

This means tool HTTP requests are no longer silently routed through container-level `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY`.

## Expected Effects

Affected generic tool HTTP callers include:

- `seek` / Tavily
- `weather` / QWeather
- future tool runtime callers using `tool_host.http_request(...)`

Expected routing:

- `DEFAULT_PROXY` set: tool HTTP requests use `DEFAULT_PROXY`.
- `DEFAULT_PROXY` empty: tool HTTP requests go direct.

This is a generic tool-host change, not a Tavily-specific branch.

## Boundaries

This change did not modify:

- `docker-compose.yml`
- `.env`
- `.env.share.example`
- Tavily `seek.py`
- Weather `weather.py`
- Telegram adapter proxy handling
- LLM model-group proxy handling

Docker/container proxy variables remain deployment/build/runtime environment settings, not the business proxy authority for tool HTTP requests.
