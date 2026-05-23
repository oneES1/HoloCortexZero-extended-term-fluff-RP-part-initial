"""Stage0 图谱缓存（关系 / 知识）骨架。

Phase A 目标：先把“缓存容器 + API 形态”落地，暂不接入现有业务逻辑。

在 Phase B/C 会把它接到：
- memory runtime 初始化链路
- _add_memory_impl(): 写穿（write-through）
- inject_memory_prompt(): snapshot 注入 + Stage1/Stage2

兼容策略：
- 优先解析 metadata.type in {relation_map, knowledge_index}（或 legacy TYPE 同义词）
- 若持久化层剥离/序列化 metadata，则尝试从结构字段(alias/target、keyword/domain)或记忆文本恢复
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .lru_cache import LRUCache

# === 常量 ===

HCZ_SELF = "HCZ_SELF"

_RELATION_MAP_TYPE_ALIASES = {"relation_map", "relationmap", "relation"}
_KNOWLEDGE_INDEX_TYPE_ALIASES = {"knowledge_index", "knowledgeindex", "knowledge"}

_RELATION_MAP_TEXT_RE = re.compile(
    r"(?:外号映射|别名映射)[:：]\s*(?P<alias>.+?)\s*->\s*(?P<target>\d+)",
    re.IGNORECASE,
)
_KNOWLEDGE_INDEX_TEXT_RE = re.compile(
    r"(?:概念索引|知识索引)[:：]\s*(?P<keyword>.+?)\s*(?:属于|->|=>)\s*(?P<domain>.+)",
    re.IGNORECASE,
)


def _safe_get(d: Any, key: str, default: Any = None) -> Any:
    try:
        if isinstance(d, dict):
            return d.get(key, default)
    except Exception:
        pass
    return default


def _coerce_list(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return [x for x in data["results"] if isinstance(x, dict)]
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


@dataclass
class GraphSnapshot:
    relations: Dict[str, str]
    concepts: Dict[str, str]

    def to_dict(self) -> Dict[str, Dict[str, str]]:
        return {
            "relations": dict(self.relations),
            "concepts": dict(self.concepts),
        }


class GraphCache:
    """进程内图谱缓存。

    - relations: alias -> target_id
    - concepts: keyword -> domain
    """

    def __init__(self, cache_size: int = 15) -> None:
        self._relations: LRUCache[str, str] = LRUCache(cache_size)
        self._concepts: LRUCache[str, str] = LRUCache(cache_size)

    @property
    def cache_size(self) -> int:
        # 目前两份 cache 始终同容量
        return self._relations.capacity

    def set_cache_size(self, cache_size: int) -> None:
        self._relations.set_capacity(cache_size)
        self._concepts.set_capacity(cache_size)

    def clear(self) -> None:
        self._relations.clear()
        self._concepts.clear()

    # ====== 更新接口（写穿 / 潜意识建议） ======

    def update_relation(self, alias: str, target_id: str) -> None:
        alias = str(alias or "").strip()
        target_id = str(target_id or "").strip()
        if not alias or not target_id:
            return
        # 安全：本工程的真实用户ID恒为“纯数字字符串”（除了 HCZ_SELF）。
        # 任何占位符（例如 User_123 / user_id / <User_ID>）都不允许进入缓存，避免污染 Stage1/Stage2。
        if target_id != HCZ_SELF and not target_id.isdigit():
            return
        self._relations.set(alias, target_id)

    def update_concept(self, keyword: str, domain: str) -> None:
        keyword = str(keyword or "").strip()
        domain = str(domain or "").strip()
        if not keyword or not domain:
            return
        self._concepts.set(keyword, domain)

    def apply_cache_updates(self, cache_updates: Optional[Mapping[str, Any]]) -> None:
        """应用潜意识输出的 cache_updates（只更新内存，不落库）。"""

        if not cache_updates or not isinstance(cache_updates, Mapping):
            return

        rel = cache_updates.get("relations")
        if isinstance(rel, dict):
            for k, v in rel.items():
                self.update_relation(str(k), str(v))

        con = cache_updates.get("concepts")
        if isinstance(con, dict):
            for k, v in con.items():
                self.update_concept(str(k), str(v))

    def snapshot(self, *, max_items: Optional[int] = None) -> GraphSnapshot:
        if max_items is None:
            max_items = self.cache_size
        return GraphSnapshot(
            relations=self._relations.snapshot(max_items=max_items),
            concepts=self._concepts.snapshot(max_items=max_items),
        )

    # ====== 解析 mem0 记录（Phase B 会在热加载/写穿调用） ======

    def _coerce_metadata_dict(self, metadata: Any) -> Optional[Dict[str, Any]]:
        if not metadata:
            return None
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            s = metadata.strip()
            if not s:
                return None
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                return None
        return None

    def _consume_relation_map_from_metadata(self, md: Dict[str, Any]) -> bool:
        alias = md.get("alias") or md.get("name")
        target = md.get("target") or md.get("target_id")
        if not alias or not target:
            return False
        self.update_relation(str(alias), str(target))
        return True

    def _consume_knowledge_index_from_metadata(self, md: Dict[str, Any]) -> bool:
        keyword = md.get("keyword") or md.get("concept") or md.get("term")
        domain = md.get("domain") or md.get("topic")
        if not keyword or not domain:
            return False
        self.update_concept(str(keyword), str(domain))
        return True

    def _consume_from_metadata(self, metadata: Any) -> bool:
        md = self._coerce_metadata_dict(metadata)
        if not md:
            return False

        md_type = md.get("type")
        if isinstance(md_type, str):
            md_type_norm = md_type.strip().lower()
            if md_type_norm in _RELATION_MAP_TYPE_ALIASES:
                return self._consume_relation_map_from_metadata(md)
            if md_type_norm in _KNOWLEDGE_INDEX_TYPE_ALIASES:
                return self._consume_knowledge_index_from_metadata(md)

        # 兼容：有些旧实现可能把大类写在 TYPE（例如 RELATION_MAP / KNOWLEDGE_INDEX）
        md_legacy_type = md.get("TYPE")
        if isinstance(md_legacy_type, str):
            md_legacy_type_norm = md_legacy_type.strip().lower()
            if md_legacy_type_norm in _RELATION_MAP_TYPE_ALIASES:
                return self._consume_relation_map_from_metadata(md)
            if md_legacy_type_norm in _KNOWLEDGE_INDEX_TYPE_ALIASES:
                return self._consume_knowledge_index_from_metadata(md)

        # 兜底：某些存储层/中间层可能会剥离 metadata.type，但保留结构字段
        # 只要 alias/target 或 keyword/domain 结构完整，就仍可恢复图谱
        if (md.get("alias") or md.get("name")) and (md.get("target") or md.get("target_id")):
            return self._consume_relation_map_from_metadata(md)
        if (md.get("keyword") or md.get("concept") or md.get("term")) and (md.get("domain") or md.get("topic")):
            return self._consume_knowledge_index_from_metadata(md)

        return False

    def _consume_from_memory_text(self, memory: str, metadata: Any = None) -> bool:
        """兜底：当 mem0 持久化后 metadata 丢失/变形时，尝试从记忆文本里恢复图谱。"""

        text = str(memory or "").strip()
        if not text:
            return False

        m = _RELATION_MAP_TEXT_RE.search(text)
        if m:
            alias = (m.group("alias") or "").strip()
            target = (m.group("target") or "").strip()
            if alias and target:
                self.update_relation(alias, target)
                return True

        m2 = _KNOWLEDGE_INDEX_TEXT_RE.search(text)
        if m2:
            keyword = (m2.group("keyword") or "").strip()
            domain = (m2.group("domain") or "").strip()
            if keyword and domain:
                self.update_concept(keyword, domain)
                return True

        return False

    def consume_memory_item(self, item: Any) -> None:
        if not item or not isinstance(item, dict):
            return
        metadata = _safe_get(item, "metadata")
        memory = _safe_get(item, "memory", "")

        if self._consume_from_metadata(metadata):
            return
        # 兜底：防止 metadata.type 被存储层过滤/剥离，导致冷启动 relations=0
        self._consume_from_memory_text(str(memory or ""), metadata=metadata)

    def write_through_from_memory(self, metadata: Dict[str, Any]) -> None:
        """写穿入口：后台写入落库成功后，调用此方法更新内存 cache。

        Phase B 会在 _add_memory_impl 写入成功后调用。
        """

        self._consume_from_metadata(metadata)

    async def load_hot_data_from_mem0(
        self,
        mem0: Any,
        *,
        user_id: str = HCZ_SELF,
        agent_id: str = "default",
        run_id: Optional[str] = None,
        limit: int = 50,
    ) -> None:
        """从 mem0 拉取热数据，填充缓存。

        说明：
        - 当前主干：HCZ_SELF 图谱热加载固定从 agent_id=default、run_id=None 读取。
        - 默认策略：优先按图谱类型过滤，只取“图谱类记忆”候选池里最近更新的 N 条，
          避免 HCZ_SELF 的其它记忆把 relation_map/knowledge_index 挤出窗口导致冷启动 relations=0。
        - 当过滤拉取结果不足时，会回退扫描一小段 unfiltered 窗口，尝试从结构字段/文本恢复。
        """

        if mem0 is None:
            return

        try:
            normalized_agent_id = "default"

            # mem0.get_all 默认 limit=100；这里我们需要的是“图谱候选池”的窗口，
            # 而不是 HCZ_SELF 全量的最近窗口，因此对图谱类型做过滤拉取。
            try:
                need = int(limit or 0)
            except Exception:
                need = 0
            if need <= 0:
                need = 50

            # 候选池窗口大小：至少 100 条，避免图谱被其它 HCZ_SELF 记忆挤出默认窗口
            fetch_limit = max(100, need * 4)

            rel_raw = await mem0.get_all(
                user_id=user_id,
                agent_id=normalized_agent_id,
                run_id=run_id,
                filters={"type": "relation_map"},
                limit=fetch_limit,
            )
            rel_items = _coerce_list(rel_raw)

            con_raw = await mem0.get_all(
                user_id=user_id,
                agent_id=normalized_agent_id,
                run_id=run_id,
                filters={"type": "knowledge_index"},
                limit=fetch_limit,
            )
            con_items = _coerce_list(con_raw)

            # best-effort：mem0 可能返回包含 created_at/updated_at 的字符串；我们尽量按时间倒序取最近 N 条
            def _ts(it: dict[str, Any]) -> float:
                md = it.get("updated_at") or it.get("created_at")
                if md is None:
                    return 0.0
                # 1) 如果是数字
                try:
                    if isinstance(md, (int, float)):
                        return float(md)
                except Exception:
                    pass
                # 1.5) 如果是 datetime 对象
                try:
                    import datetime as _dt

                    if isinstance(md, _dt.datetime):
                        dt = md
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=_dt.timezone.utc)
                        return dt.timestamp()
                except Exception:
                    pass
                # 2) 如果是字符串：尽量解析 ISO 时间
                if isinstance(md, str):
                    try:
                        # 优先用 dateutil（项目已依赖），兼容更多时间格式；失败再回退标准库
                        from dateutil import parser as _dtparser  # type: ignore

                        dt = _dtparser.parse(md)
                        if dt.tzinfo is None:
                            import datetime as _dt

                            dt = dt.replace(tzinfo=_dt.timezone.utc)
                        return dt.timestamp()
                    except Exception:
                        pass
                    try:
                        # 标准库兜底
                        import datetime as _dt

                        s = md.strip()
                        # 兼容 Z
                        if s.endswith("Z"):
                            s = s[:-1] + "+00:00"
                        dt = _dt.datetime.fromisoformat(s)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=_dt.timezone.utc)
                        return dt.timestamp()
                    except Exception:
                        return 0.0
                return 0.0

            def _dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
                seen: set[str] = set()
                out: list[dict[str, Any]] = []
                for it in items:
                    mid = it.get("id")
                    key = ("id:" + str(mid)) if mid is not None else ("mem:" + str(it.get("memory") or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(it)
                return out

            # 回退：如果过滤拉取不足以填满缓存，再从 unfiltered 最近窗口里做一次“图谱判定”补齐。
            if len(rel_items) < need or len(con_items) < need:
                try:
                    raw_all = await mem0.get_all(
                        user_id=user_id,
                        agent_id=normalized_agent_id,
                        run_id=run_id,
                        limit=max(fetch_limit, 300),
                    )
                    items_all = _coerce_list(raw_all)
                    for it in items_all:
                        if not isinstance(it, dict):
                            continue
                        meta = _safe_get(it, "metadata")
                        mem = _safe_get(it, "memory", "")
                        md = self._coerce_metadata_dict(meta)

                        # relation candidates
                        is_rel = False
                        is_con = False
                        if md:
                            md_type = ""
                            t = md.get("type")
                            if isinstance(t, str):
                                md_type = t.strip().lower()
                            else:
                                legacy = md.get("TYPE")
                                if isinstance(legacy, str):
                                    md_type = legacy.strip().lower()
                            if md_type in _RELATION_MAP_TYPE_ALIASES:
                                is_rel = True
                            elif md_type in _KNOWLEDGE_INDEX_TYPE_ALIASES:
                                is_con = True
                            elif (md.get("alias") or md.get("name")) and (md.get("target") or md.get("target_id")):
                                is_rel = True
                            elif (md.get("keyword") or md.get("concept") or md.get("term")) and (md.get("domain") or md.get("topic")):
                                is_con = True

                        if not (is_rel or is_con):
                            mem_s = str(mem or "").strip()
                            if _RELATION_MAP_TEXT_RE.search(mem_s):
                                is_rel = True
                            elif _KNOWLEDGE_INDEX_TEXT_RE.search(mem_s):
                                is_con = True

                        if is_rel:
                            rel_items.append(it)
                        if is_con:
                            con_items.append(it)
                except Exception:
                    pass

            rel_items = _dedup(rel_items)
            con_items = _dedup(con_items)

            # 分类型挑选：取各自候选池里“最近更新”的 N 条，填满 relations/concepts 两个独立缓存
            rel_items.sort(key=_ts)
            con_items.sort(key=_ts)

            if need > 0:
                rel_items = rel_items[-need:]
                con_items = con_items[-need:]

            for it in rel_items:
                self.consume_memory_item(it)
            for it in con_items:
                self.consume_memory_item(it)
        except Exception:
            # 热加载失败不应阻断运行时启动；后续按需检索/写穿会逐渐填充
            return


# 模块级单例（后续业务侧直接 import graph_cache 使用）
graph_cache = GraphCache(cache_size=15)
