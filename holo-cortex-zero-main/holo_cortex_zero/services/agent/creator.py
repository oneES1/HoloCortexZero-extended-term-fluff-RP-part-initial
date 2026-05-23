from typing import Any, Dict, List, Literal

from .context_blocks import merge_context_block_plans


class OpenAIChatMessage:
    """OpenAI 聊天消息"""

    def __init__(
        self,
        role: Literal["user", "assistant", "system"],
        content: List[Dict[str, Any]],
        transport_meta: Dict[str, Any] | None = None,
    ):
        self.role: Literal["user", "assistant", "system"] = role
        self.content = content
        self.transport_meta: Dict[str, Any] = dict(transport_meta or {})

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        将连续的文本内容进行聚合，例如:
        [{"type": "text", "text": "你好 "}, {"type": "text", "text": "世界"}]
        会被聚合为:
        [{"type": "text", "text": "你好 世界"}]
        """

        if all(_c["type"] == "text" for _c in self.content):
            return {"role": self.role, "content": "".join(_c["text"] for _c in self.content)}

        merged_content: List[Dict[str, Any]] = []
        current_text = ""
        for segment in self.content:
            if segment["type"] == "text":
                current_text += segment["text"]
            else:
                if current_text:
                    merged_content.append({"type": "text", "text": current_text})
                    current_text = ""
                merged_content.append(segment)
        if current_text:
            merged_content.append({"type": "text", "text": current_text})
        return {"role": self.role, "content": merged_content}

    @classmethod
    def create_empty(cls, role: Literal["user", "assistant", "system"]) -> "OpenAIChatMessage":
        """创建空消息"""
        return cls(role, [])

    def add(self, segment: Dict[str, Any]) -> "OpenAIChatMessage":
        """添加内容片段"""
        self.content.append(segment)
        return self

    def extend(self, other: "OpenAIChatMessage") -> "OpenAIChatMessage":
        """合并消息"""
        if self.role != other.role:
            raise ValueError("消息角色不一致")
        if isinstance(other.content, str):
            other.content = [ContentSegment.text_content(other.content)]
        merged_meta = dict(self.transport_meta)
        other_meta = dict(other.transport_meta)
        self_context_block_plan = merged_meta.get("context_block_plan") if isinstance(merged_meta, dict) else None
        other_context_block_plan = other_meta.get("context_block_plan") if isinstance(other_meta, dict) else None
        merged_meta.update(other_meta)
        if self_context_block_plan or other_context_block_plan:
            merged_meta["context_block_plan"] = merge_context_block_plans(
                self_context_block_plan if isinstance(self_context_block_plan, dict) else None,
                other_context_block_plan if isinstance(other_context_block_plan, dict) else None,
            )
        return OpenAIChatMessage(self.role, self.content + other.content, transport_meta=merged_meta)


class ContentSegment:
    """内容片段生成器"""

    @staticmethod
    def image_content(image_url: str) -> Dict[str, Any]:
        """生成图片内容片段"""
        return {"type": "image_url", "image_url": {"url": image_url}}

    @staticmethod
    def text_content(text: str) -> Dict[str, Any]:
        """生成文本内容片段"""
        return {"type": "text", "text": text}
