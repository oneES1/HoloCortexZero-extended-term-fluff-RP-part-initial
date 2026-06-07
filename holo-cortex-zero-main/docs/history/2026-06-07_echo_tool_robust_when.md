# Echo tool robust when parsing

## Change
- Tool registry now forwards unknown call arguments only to handlers that explicitly declare `**kwargs`.
- The `echo` tool accepts missing `when` and resolves it from malformed LLM argument names such as `echo`, `seconds`, or other unknown fields.
- `reason` keeps normal behavior and can fall back to explicit text-like unknown fields when omitted.

## Verification
- Container compile check passed for touched modules.
- Focused probe verified `when`, `echo`, `seconds`, arbitrary unknown time field, invalid unknown field failure, and registry `**kwargs` isolation.
