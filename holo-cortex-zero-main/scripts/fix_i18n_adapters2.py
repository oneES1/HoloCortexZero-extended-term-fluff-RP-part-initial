#!/usr/bin/env python3
"""Patch adapter config files with i18n_title / i18n_description."""

import re
from pathlib import Path

TITLE_EN = {
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


def build_i18n_block(title: str, description: str, indent: str) -> str:
    en_title = TITLE_EN.get(title, title)
    en_desc = DESC_EN.get(description, description) if description else ""
    lines = [f"{indent}i18n_title=i18n_text("]
    lines.append(f'{indent}    zh_CN="{title}",')
    lines.append(f'{indent}    en_US="{en_title}",')
    lines.append(f"{indent}),")
    if description:
        lines.append(f"{indent}i18n_description=i18n_text(")
        lines.append(f'{indent}    zh_CN="{description}",')
        lines.append(f'{indent}    en_US="{en_desc}",')
        lines.append(f"{indent}),")
    return "\n".join(lines)


def patch_adapter_file(filepath: Path) -> int:
    content = filepath.read_text()
    lines = content.split("\n")
    result = []
    i = 0
    modified = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\s+)([A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=\s*Field\(', line)
        if not m:
            result.append(line)
            i += 1
            continue

        indent = m.group(1)
        start = i
        paren_depth = line.count("(") - line.count(")")
        j = i + 1
        while j < len(lines) and paren_depth > 0:
            paren_depth += lines[j].count("(") - lines[j].count(")")
            j += 1
        block_lines = lines[start:j]
        block = "\n".join(block_lines)

        if "i18n_title" in block or "is_hidden=True" in block:
            result.extend(block_lines)
            i = j
            continue

        title_m = re.search(r'title="([^"]+)"', block)
        desc_m = re.search(r'description="((?:[^"\\]|\\.)*)"', block)
        title = title_m.group(1) if title_m else ""
        description = desc_m.group(1).replace('\\"', '"') if desc_m else ""

        if not title or title not in TITLE_EN:
            result.extend(block_lines)
            i = j
            continue

        i18n_block = build_i18n_block(title, description, indent + "    ")

        # Case 1: json_schema_extra=ExtraField(...).model_dump()
        if "json_schema_extra=ExtraField(" in block:
            new_block = block.replace(
                "json_schema_extra=ExtraField(",
                f"json_schema_extra=ExtraField(\n{i18n_block}\n{indent}",
                1,
            )
            result.extend(new_block.split("\n"))
            modified += 1
            i = j
            continue

        # Case 2: json_schema_extra={...}
        dict_match = re.search(r'json_schema_extra=\{([^}]*)\}', block)
        if dict_match:
            existing = dict_match.group(1).strip()
            i18n_part = i18n_block.replace("i18n_title=", '"i18n_title": ').replace("i18n_description=", '"i18n_description": ')
            if existing:
                replacement = f'json_schema_extra={{{existing}, {i18n_part}\n{indent}}}'
            else:
                replacement = f'json_schema_extra={{{i18n_part}\n{indent}}}'
            new_block = block[:dict_match.start()] + replacement + block[dict_match.end():]
            result.extend(new_block.split("\n"))
            modified += 1
            i = j
            continue

        # Case 3: no json_schema_extra
        extra = f"json_schema_extra=ExtraField(\n{i18n_block}\n{indent}).model_dump(),"
        insert_idx = len(block_lines) - 1
        while insert_idx > 0 and ")" not in block_lines[insert_idx]:
            insert_idx -= 1
        block_lines.insert(insert_idx, indent + extra)
        result.extend(block_lines)
        modified += 1
        i = j

    filepath.write_text("\n".join(result))
    return modified


if __name__ == "__main__":
    root = Path("/home/ubuntu/hcz-deploy/holo-cortex-zero-main")
    for fp in [
        root / "holo_cortex_zero/adapters/telegram/config.py",
        root / "holo_cortex_zero/adapters/matrix/config.py",
        root / "holo_cortex_zero/adapters/onebot_v11/adapter.py",
    ]:
        n = patch_adapter_file(fp)
        print(f"Patched {n} fields in {fp}")
