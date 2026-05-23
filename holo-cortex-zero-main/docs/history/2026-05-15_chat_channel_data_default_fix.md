# chat_channel data default fix

Date: 2026-05-15

## Symptom

Matrix private message ingestion failed while creating the first HCZ channel:

```text
null value in column "data" of relation "chat_channel" violates not-null constraint
```

The failing row had correct Matrix identity mapping:

```text
adapter_key = matrix
channel_id = private_<ADVANCED_USER_ID>
channel_name = Matrix 私聊: 海泡菜
channel_type = private
chat_key = matrix-private_<ADVANCED_USER_ID>
data = null
```

## Root Cause

The live PostgreSQL schema has a required `chat_channel.data` column:

```text
data text NOT NULL
```

Existing channel rows use:

```json
{}
```

The `DBChatChannel` ORM model did not include the `data` field, so new channel creation through `DBChatChannel.create(...)` omitted it and PostgreSQL received `null`.

This is a schema/model drift, not a Matrix-specific identity bug.

## Fix

Restore the model field:

```python
data = fields.TextField(default="{}", description="频道数据")
```

Also set the database-level default:

```sql
ALTER TABLE chat_channel ALTER COLUMN data SET DEFAULT '{}';
```

The value `{}` means the channel has no extra metadata. Matrix room mapping remains in the Matrix adapter state file and is not stored in `chat_channel.data`.

## Rollback

Code rollback:

```bash
git revert <fix-commit>
```

Database default rollback:

```sql
ALTER TABLE chat_channel ALTER COLUMN data DROP DEFAULT;
```
