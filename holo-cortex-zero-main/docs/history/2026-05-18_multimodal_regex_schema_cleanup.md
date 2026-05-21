# 2026-05-18 多模态切组正则列表主干收口

## 问题复盘

- `AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS` 的真实语义是“正则表达式列表”。
- 字段类型本来就是 `List[str]`，但额外打了 `is_textarea=true`，导致 schema 同时表达了“列表编辑”和“多行文本”两套互相冲突的语义。
- 同领域已有主干 `AI_CHAT_TRIGGER_REGEX` / `AI_CHAT_IGNORE_REGEX` 都走标准列表编辑，不走 textarea。

## 本次收口

- 删除 `AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS` 上错误的 `is_textarea` 元数据。
- 改为与其他正则列表一致的标准列表 schema，补 `sub_item_name="表达式"`。
- 删除前端为兼容错误 schema 临时加入的 `List[str] + textarea` 特判逻辑。

## 结论

- 这项配置应当回到现有“列表编辑主干”，而不是继续扩展前端去兼容错误 schema。
- 同类配置以后统一按 `List[str]` 列表处理，避免再出现并行语义。
