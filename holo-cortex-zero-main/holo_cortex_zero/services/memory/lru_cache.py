"""轻量 LRU Cache 工具。

Phase A 目标：提供一个可复用、可测试、无业务耦合的 LRU 容器，供 Stage0 图谱缓存使用。

实现策略：
- 使用 OrderedDict 维护访问顺序（move_to_end）。
- 每个 key 记录 last_hit（满足 RFC 的“内存级 LRU last_hit_timestamp”表述）。
- 超出容量时淘汰最久未使用（OrderedDict 头部）。
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Generic, Iterable, Iterator, MutableMapping, Optional, Tuple, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class LRUEntry(Generic[V]):
    value: V
    last_hit: float


class LRUCache(Generic[K, V]):
    """一个简单的 LRU Cache。

    - get/set 会自动 touch；
    - touch 会刷新 last_hit 并将 key 移到队尾；
    - 超容量自动淘汰最旧的 key。
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._data: "OrderedDict[K, LRUEntry[V]]" = OrderedDict()

    @property
    def capacity(self) -> int:
        return self._capacity

    def set_capacity(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._evict_if_needed()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: K) -> bool:
        return key in self._data

    def keys(self) -> Iterable[K]:
        return self._data.keys()

    def items(self) -> Iterable[Tuple[K, V]]:
        for k, entry in self._data.items():
            yield k, entry.value

    def get(self, key: K, default: Optional[V] = None, *, touch: bool = True) -> Optional[V]:
        entry = self._data.get(key)
        if entry is None:
            return default
        if touch:
            self.touch(key)
            entry = self._data.get(key)
        return entry.value if entry is not None else default

    def set(self, key: K, value: V) -> None:
        now = time.time()
        if key in self._data:
            # 更新后视为一次命中
            self._data[key] = LRUEntry(value=value, last_hit=now)
            self._data.move_to_end(key)
        else:
            self._data[key] = LRUEntry(value=value, last_hit=now)
            self._data.move_to_end(key)
        self._evict_if_needed()

    def touch(self, key: K) -> bool:
        if key not in self._data:
            return False
        entry = self._data[key]
        self._data[key] = LRUEntry(value=entry.value, last_hit=time.time())
        self._data.move_to_end(key)
        return True

    def pop(self, key: K, default: Optional[V] = None) -> Optional[V]:
        entry = self._data.pop(key, None)
        if entry is None:
            return default
        return entry.value

    def clear(self) -> None:
        self._data.clear()

    def snapshot(self, *, max_items: Optional[int] = None) -> Dict[K, V]:
        """导出一个“只包含 value”的快照。

        默认返回“最近使用优先”的尾部若干条，避免 prompt 过大。
        """

        if max_items is None or max_items <= 0:
            max_items = len(self._data)

        # OrderedDict 尾部是最新使用
        items = list(self._data.items())
        tail = items[-max_items:]
        return {k: entry.value for k, entry in tail}

    def _evict_if_needed(self) -> None:
        while len(self._data) > self._capacity:
            # popitem(last=False) -> pop oldest
            self._data.popitem(last=False)
