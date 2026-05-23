#!/usr/bin/env python3
"""Bulk-add i18n_title / i18n_description to backend config fields."""

import re
from pathlib import Path

# --- Translation dictionary: Chinese title -> English title ---
TITLE_EN = {
    "对智能体的统一ID标识": "Advanced User ID",
    "你对智能体的统一昵称": "Advanced User Display Name",
    "普通 context 回忆刷新间隔": "Normal Context Memory Recall Refresh Interval",
    "普通 context 重置阈值": "Normal Context Reset Threshold",
    "普通 context 重置保留条数": "Normal Context Reset Keep Messages",
    "启用群聊回复判断": "Enable Group Chat Reply Judgment",
    "群聊回复判断LLM": "Group Chat Reply Judgment LLM",
    "Timeline 压缩LLM": "Timeline Compression LLM",
    "群聊回复判断历史条数": "Group Chat Reply Judgment History Messages",
    "群聊回复判断超时秒数": "Group Chat Reply Judgment Timeout (seconds)",
    "群聊 judge 激活窗口秒数": "Group Chat Judge Active Window (seconds)",
    "启用多模态正则切组": "Enable Multimodal Regex Switch",
    "多模态切组正则列表": "Multimodal Switch Regex List",
    "多模态正则扫描消息数": "Multimodal Regex Scan Message Count",
    "多模态媒体最大秒数": "Multimodal Media Max Seconds",
    "多模态音频上限": "Multimodal Audio Max Count",
    "记忆管理模型": "Memory Management Model",
    "记忆向量嵌入模型": "Text Embedding Model",
    "记忆嵌入维度": "Text Embedding Dimension",
    "启用潜意识记忆路由": "Enable Subconscious Memory Routing",
    "潜意识LLM": "Subconscious LLM",
    "潜意识超时秒数": "Subconscious Timeout (seconds)",
    "潜意识缓存大小": "Subconscious Cache Size",
    "记忆注入每用户最大条数": "Prompt Inject Max Items Per User",
    "启用系统自动记忆": "Enable Auto Memory",
    "自动记忆LLM": "Auto Memory LLM",
    "自动记忆触发消息数": "Auto Memory Trigger Message Count",
    "自动记忆取样消息数": "Auto Memory Recent Message Count",
    "自动记忆最大写入条数": "Auto Memory Max Tool Calls",
    "自动记忆 tool_choice": "Auto Memory Tool Choice",
    "记录自动记忆 Payload": "Log Auto Memory Payload",
    "启用系统自设图": "Enable Self Image",
    "自动注入印象图": "Auto Inject Impression Image",
    "显示自设图直传路径": "Show Self Image Direct Path",
    "印象图路径": "Impression Image Path",
    "bot 自设图路径": "Bot Persona Image Path",
    "你的日常照路径": "User Daily Image Path",
    "你的写真照路径": "User Portrait Image Path",
    "启用系统语音后处理": "Enable System Voice Post-processing",
    "启用系统表情后处理": "Enable System Emoji Post-processing",
    "系统表情触发概率": "System Emoji Trigger Probability",
    "系统表情嵌入模型": "System Emoji Embedding Model",
    "系统表情宿主机目录": "System Emoji Host Directory",
    "系统语音文本长度阈值": "System Voice Short Text Max Length",
    "系统语音触发概率": "System Voice Trigger Probability",
    "系统语音允许适配器": "System Voice Allowed Adapters",
    "系统语音嵌入模型": "System Voice Embedding Model",
    "系统语音 API Key": "System Voice API Key",
    "系统语音模型": "System Voice Model",
    "系统语音默认音色": "System Voice Default Voice ID",
    "系统语音 WebSocket 地址": "System Voice WebSocket URL",
    "系统语音超时毫秒": "System Voice Timeout (ms)",
    "系统语音采样率": "System Voice Sample Rate",
    "系统语音语言提示": "System Voice Language Hints",
    "系统语音固定语速": "System Voice Speech Rate",
    "系统语音固定音调": "System Voice Pitch Rate",
    "系统语音前置 instruction": "System Voice Instruction Prefix",
    "系统语音 guidance 库 JSON": "System Voice Guidance Library JSON",
    "系统语音后台并发": "System Voice Max Background Concurrency",
    "高级文件系统根目录": "Advanced File System Root",
    "普通用户图片隔离接收": "Normal User Image Quarantine",
    "引用消息保留媒体": "Reference Include Media",
    "引用摘要最大长度": "Reference Text Max Length",
    # Adapter fields
    "Bot Token": "Bot Token",
    "代理地址": "Proxy URL",
    "你的 TG ID": "Your TG User ID",
    "自动接入私聊": "Auto Accept Private Chat",
    "Matrix Homeserver URL": "Matrix Homeserver URL",
    "Matrix Proxy URL": "Matrix Proxy URL",
    "Bot Matrix User ID": "Bot Matrix User ID",
    "Bot Password": "Bot Password",
    "Bot Access Token": "Bot Access Token",
    "Device ID": "Device ID",
    "Crypto Store Path": "Crypto Store Path",
    "Ignore Unverified Devices": "Ignore Unverified Devices",
    "你的 Element(Matrix客户端) ID": "Your Element (Matrix) ID",
    "自动加入私聊邀请": "Auto Join Private Invite",
    "自动加入群聊邀请": "Auto Join Group Invite",
    "Sync 超时毫秒": "Sync Timeout (ms)",
    "请求超时秒": "Request Timeout (seconds)",
    "房间映射状态文件": "Room Mapping State File",
    "启用 @用户 功能": "Enable @User Feature",
    "显示处理中表情反馈": "Show Processing Emoji Feedback",
    "机器人 QQ 号": "Bot QQ Number",
    "你的QQ ID": "Your QQ ID",
    "自动接受私聊好友请求": "Auto Accept Private Friend Request",
    "自动接受群聊邀请": "Auto Accept Group Invite",
    "NapCat WebUI 访问地址": "NapCat WebUI Access URL",
    "NapCat 内部代理地址": "NapCat Internal Proxy URL",
    "NapCat 容器名称": "NapCat Container Name",
}

DESC_EN = {
    "普通 context 每累计多少次用户触发才重新计算一次潜意识与 Stage1/Stage2 回忆；其余轮次复用上次缓存。": "How many user triggers before recalculating subconscious and Stage1/Stage2 memory for normal context; otherwise reuse cached results.",
    "普通 context 原始上下文累计到多少条后，一次性回收旧历史。": "Normal context raw history message count threshold before one-time old history cleanup.",
    "普通 context 达到重置阈值后保留的最近原始消息条数。": "Number of recent raw messages kept after normal context reaches reset threshold.",
    "仅对普通群聊 context 启用 LLM 回复判断；私聊与高级用户 context 不受影响。": "Enable LLM reply judgment for normal group chat contexts only; private chats and advanced users are unaffected.",
    "系统级 ai_reply 群聊回复判断专用的 chat.completions LLM。": "Dedicated chat.completions LLM for system-level ai_reply group chat judgment.",
    "时间线摘要压缩专用 LLM；必须显式配置有效 LLM，不再隐式回退到 default。": "Dedicated LLM for timeline summary compression; must be explicitly configured, no implicit fallback to default.",
    "普通群聊回复判断时，最多读取多少条纯文本聊天历史。": "Maximum number of plain text chat history messages read during normal group chat reply judgment.",
    "普通群聊回复判断辅助 LLM 的超时时间（秒）。": "Timeout for the auxiliary LLM used in normal group chat reply judgment (seconds).",
    "群聊出现一次主动唤起（@、关键词、随机或系统触发）后，后续多长时间内才允许调用 judge LLM；设为 0 表示恢复旧行为、始终允许 judge。": "After an active invocation in group chat, how long before judge LLM can be called again; 0 restores old behavior (always allow).",
    "仅对高级用户 context 生效；命中正则时切换到多模态 LLM。": "Only affects advanced user contexts; switches to multimodal LLM when regex matches.",
    "高级用户多模态切组使用的正则列表，按配置顺序匹配，任一命中即切组。": "Regex list for advanced user multimodal group switching; matches in order, first hit switches group.",
    "高级用户多模态正则扫描的最近纯文本用户消息条数。": "Number of recent plain text user messages scanned by advanced user multimodal regex.",
    "Gemini 路径下音频转码与视频抽音轨时允许保留的最长秒数。": "Maximum seconds allowed for audio transcoding and video audio track extraction in Gemini path.",
    "Gemini 路径下最多保留多少个最近音频 part；超限按时间顺序砍最老的。": "Maximum recent audio parts to retain in Gemini path; excess removed oldest first.",
    "用于将传入记忆做整理与仲裁的对话 LLM。": "Dialogue LLM used for organizing and arbitrating incoming memories.",
    "用于记忆嵌入与检索的 embedding LLM。": "Embedding LLM used for memory embedding and retrieval.",
    "用于表情标签语义匹配的 embedding 模型。": "Embedding model used for semantic matching of emoji labels.",
    "用于 guidance 匹配的 embedding 模型。": "Embedding model used for guidance matching.",
    "记忆向量嵌入维度。": "Memory vector embedding dimension.",
    "启用后会加载 Stage0 图谱缓存并执行 Stage1 路由。": "When enabled, loads Stage0 graph cache and executes Stage1 routing.",
    "用于 Stage1 潜意识路由与意图生成的 LLM。": "LLM used for Stage1 subconscious routing and intent generation.",
    "潜意识模型调用超时阈值。": "Subconscious model call timeout threshold.",
    "Stage0 图谱缓存容量上限。": "Stage0 graph cache capacity limit.",
    "最终注入主模型前，每个用户最多保留多少条记忆。": "Maximum memories per user before injecting into main model.",
    "识别近期记忆时允许的时间前瞻容忍窗口。": "Time forward tolerance window when identifying recent memories.",
    "Telegram Bot API Token": "Telegram Bot API Token",
    "Telegram API 访问代理，支持 http/https/socks5 协议.空白表示不使用代理": "Telegram API access proxy, supports http/https/socks5. Leave blank for no proxy.",
    "Telegram 平台侧高级用户数字 user_id；框架内高级 ID 由 ADVANCED_USER_ID 决定。": "Telegram platform-side advanced user numeric ID; framework advanced ID is determined by ADVANCED_USER_ID.",
    "Telegram Bot 没有接受私聊邀请动作；开启表示接收私聊 update。Telegram 也没有自动加入群聊 API，bot 被拉入群后才会收到群消息。是否回复由聊天频道 is_active 和触发逻辑决定。": "Telegram Bot has no private chat acceptance action; enabling means receiving private chat updates. Telegram also has no auto group join API; the bot only receives group messages after being added. Whether to reply is determined by channel is_active and trigger logic.",
    "Matrix homeserver client API base URL.": "Matrix homeserver client API base URL.",
    "Matrix adapter proxy URL. Empty means direct connection.": "Matrix adapter proxy URL. Empty means direct connection.",
    "Matrix bot account, e.g. @hcz:holocortexzero.com.": "Matrix bot account, e.g. @hcz:holocortexzero.com.",
    "Bot password used when BOT_ACCESS_TOKEN is empty.": "Bot password used when BOT_ACCESS_TOKEN is empty.",
    "Matrix access token. Preferred for long-running production; SDK restore_login will use DEVICE_ID with this token.": "Matrix access token. Preferred for long-running production; SDK restore_login will use DEVICE_ID with this token.",
    "Stable Matrix device id for SDK login and E2EE crypto store.": "Stable Matrix device ID for SDK login and E2EE crypto store.",
    "matrix-nio E2EE crypto store path. Relative paths are stored under the Matrix adapter config directory.": "matrix-nio E2EE crypto store path. Relative paths are stored under the Matrix adapter config directory.",
    "When sending to encrypted rooms, allow matrix-nio to send to unverified devices. Recommended true for open deployments without manual device verification.": "When sending to encrypted rooms, allow matrix-nio to send to unverified devices. Recommended true for open deployments without manual device verification.",
    "Matrix 平台侧高级用户 ID；框架内高级 ID 由 ADVANCED_USER_ID 决定。": "Matrix platform-side advanced user ID; framework advanced ID is determined by ADVANCED_USER_ID.",
    "自动加入私聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。": "Auto join private chat invites. Whether to reply is determined by channel is_active and trigger logic.",
    "默认关闭；开启后自动加入群聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。": "Default off; enable to auto join group chat invites. Whether to reply is determined by channel is_active and trigger logic.",
    "Matrix /sync 长轮询超时时间。": "Matrix /sync long-polling timeout.",
    "Matrix HTTP 请求超时。": "Matrix HTTP request timeout.",
    "保存 HCZ channel_id 到 Matrix room_id 的映射；位于 adapter config 目录。": "Stores HCZ channel_id to Matrix room_id mapping; located in adapter config directory.",
    "关闭后 AI 发送的 @用户 消息将被解析为纯文本用户名，避免反复打扰用户": "When disabled, AI @user messages will be parsed as plain text usernames to avoid repeatedly disturbing users.",
    "当 AI 开始处理消息时，对应消息会显示处理中表情反馈": "When AI starts processing a message, the corresponding message will show a processing emoji feedback.",
    "QQ/OneBot 平台侧高级用户 QQ 号；框架内高级 ID 由 ADVANCED_USER_ID 决定。": "QQ/OneBot platform-side advanced user QQ number; framework advanced ID is determined by ADVANCED_USER_ID.",
    "自动接受真实高级用户和普通用户的好友请求。是否回复由聊天频道 is_active 和触发逻辑决定。": "Auto accept friend requests from real advanced users and normal users. Whether to reply is determined by channel is_active and trigger logic.",
    "默认不自动接受群聊邀请或加群请求。": "By default, do not auto accept group chat invites or join requests.",
    "NapCat 的 WebUI 外部访问路径。默认走 HCZ 内置 /napcat 反代，不需要暴露 NapCat 端口。": "NapCat WebUI external access path. Defaults to HCZ built-in /napcat reverse proxy; no need to expose NapCat port.",
    "HCZ 后端访问 NapCat WebUI 的内部地址；Docker 部署默认走同一 compose 网络。": "HCZ backend internal address for accessing NapCat WebUI; Docker deployments default to the same compose network.",
}


def build_i18n_block(title: str, description: str, indent: str = "            ") -> str:
    """Generate i18n_title + i18n_description ExtraField arguments."""
    en_title = TITLE_EN.get(title, title)
    en_desc = DESC_EN.get(description, description) if description else ""

    lines = [f'{indent}i18n_title=i18n_text(']
    lines.append(f'{indent}    zh_CN="{title}",')
    lines.append(f'{indent}    en_US="{en_title}",')
    lines.append(f'{indent}),')
    if description:
        lines.append(f'{indent}i18n_description=i18n_text(')
        lines.append(f'{indent}    zh_CN="{description}",')
        lines.append(f'{indent}    en_US="{en_desc}",')
        lines.append(f'{indent}),')
    return "\n".join(lines)


def patch_core_config(filepath: Path) -> int:
    """Patch holo_cortex_zero/core/config.py"""
    content = filepath.read_text()
    original = content

    # Strategy: find all Field(...) blocks in CoreConfig (after line ~105)
    lines = content.split("\n")
    result_lines = []
    i = 0
    modified = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\s+)([A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=\s*Field\(', line)
        if m and i + 1 >= 105:  # CoreConfig starts around line 105
            indent = m.group(1)
            field_name = m.group(2)
            start = i
            paren_depth = line.count("(") - line.count(")")
            j = i + 1
            while j < len(lines) and paren_depth > 0:
                paren_depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            block = "\n".join(lines[start:j])
            if "i18n_title" in block or "is_hidden=True" in block:
                result_lines.extend(lines[start:j])
                i = j
                continue

            title_m = re.search(r'title="([^"]+)"', block)
            desc_m = re.search(r'description="((?:[^"\\]|\\.)*)"', block)
            title = title_m.group(1) if title_m else ""
            description = desc_m.group(1).replace('\\"', '"') if desc_m else ""

            if title and title in TITLE_EN:
                i18n_block = build_i18n_block(title, description, indent + "    ")
                # Check if json_schema_extra already exists
                if "json_schema_extra" in block:
                    # Replace json_schema_extra=ExtraField().model_dump() or similar
                    # We look for ExtraField( ... ).model_dump()
                    new_block = re.sub(
                        r'ExtraField\([^)]*\)\.model_dump\(\)',
                        f"ExtraField(\n{indent}    {i18n_block.strip()}\n{indent}).model_dump()",
                        block,
                    )
                    # If regex didn't match (e.g. plain dict), skip
                    if new_block == block:
                        result_lines.extend(lines[start:j])
                    else:
                        result_lines.extend(new_block.split("\n"))
                        modified += 1
                else:
                    # Add json_schema_extra before the final )
                    # Find the last ) that closes Field
                    extra = f'json_schema_extra=ExtraField(\n{indent}    {i18n_block.strip()}\n{indent}).model_dump(),'
                    # Insert before the last closing paren line
                    block_lines = block.split("\n")
                    # Find the line with the final closing paren
                    last_paren_idx = len(block_lines) - 1
                    while last_paren_idx > 0 and ")" not in block_lines[last_paren_idx]:
                        last_paren_idx -= 1
                    # Insert before it
                    block_lines.insert(last_paren_idx, indent + extra)
                    result_lines.extend(block_lines)
                    modified += 1
                i = j
                continue

            result_lines.extend(lines[start:j])
            i = j
            continue

        result_lines.append(line)
        i += 1

    filepath.write_text("\n".join(result_lines))
    return modified


def patch_adapter_file(filepath: Path) -> int:
    """Patch adapter config files."""
    content = filepath.read_text()
    lines = content.split("\n")
    result_lines = []
    i = 0
    modified = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\s+)([A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=\s*Field\(', line)
        if m:
            indent = m.group(1)
            start = i
            paren_depth = line.count("(") - line.count(")")
            j = i + 1
            while j < len(lines) and paren_depth > 0:
                paren_depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            block = "\n".join(lines[start:j])
            if "i18n_title" in block or "is_hidden=True" in block:
                result_lines.extend(lines[start:j])
                i = j
                continue

            title_m = re.search(r'title="([^"]+)"', block)
            desc_m = re.search(r'description="((?:[^"\\]|\\.)*)"', block)
            title = title_m.group(1) if title_m else ""
            description = desc_m.group(1).replace('\\"', '"') if desc_m else ""

            if title and title in TITLE_EN:
                i18n_block = build_i18n_block(title, description, indent + "    ")
                if "json_schema_extra" in block:
                    new_block = re.sub(
                        r'json_schema_extra=\{([^}]*)\}',
                        f'json_schema_extra={{\1, {i18n_block.strip()}}}',
                        block,
                    )
                    if new_block == block:
                        # Try ExtraField pattern
                        new_block = re.sub(
                            r'ExtraField\(([^)]*)\)\.model_dump\(\)',
                            f"ExtraField(\n{indent}    {i18n_block.strip()}\n{indent}).model_dump()",
                            block,
                        )
                    if new_block != block:
                        result_lines.extend(new_block.split("\n"))
                        modified += 1
                        i = j
                        continue
                    result_lines.extend(lines[start:j])
                else:
                    extra = f'json_schema_extra=ExtraField(\n{indent}    {i18n_block.strip()}\n{indent}).model_dump(),'
                    block_lines = block.split("\n")
                    last_paren_idx = len(block_lines) - 1
                    while last_paren_idx > 0 and ")" not in block_lines[last_paren_idx]:
                        last_paren_idx -= 1
                    block_lines.insert(last_paren_idx, indent + extra)
                    result_lines.extend(block_lines)
                    modified += 1
                    i = j
                    continue

            result_lines.extend(lines[start:j])
            i = j
            continue

        result_lines.append(line)
        i += 1

    filepath.write_text("\n".join(result_lines))
    return modified


if __name__ == "__main__":
    root = Path("/home/ubuntu/hcz-deploy/holo-cortex-zero-main")
    n = patch_core_config(root / "holo_cortex_zero/core/config.py")
    print(f"Patched {n} fields in core/config.py")
    for fp in [
        root / "holo_cortex_zero/adapters/telegram/config.py",
        root / "holo_cortex_zero/adapters/matrix/config.py",
        root / "holo_cortex_zero/adapters/onebot_v11/adapter.py",
    ]:
        n = patch_adapter_file(fp)
        print(f"Patched {n} fields in {fp}")
