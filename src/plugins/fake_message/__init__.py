from asyncio import log

from nonebot import on_message, on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

TARGET_GROUP_ID = 658521872


def _parse_forward_node(line: str, fallback_user_id: int):
    line = line.strip()
    if not line:
        return None

    if "|" not in line:
        raise ValueError("每条节点需要使用「昵称|内容」格式")

    nickname, payload = line.split("|", 1)
    nickname = nickname.strip()
    payload = payload.strip()
    if not nickname or not payload:
        raise ValueError("节点昵称和内容不能为空")

    user_id = fallback_user_id
    content = payload

    if "|" in payload:
        maybe_content, maybe_user_id = payload.rsplit("|", 1)
        if maybe_user_id.strip().isdigit():
            content = maybe_content.strip()
            user_id = int(maybe_user_id.strip())

    if not content:
        raise ValueError("节点内容不能为空")

    return MessageSegment.node_custom(
        user_id=user_id,
        nickname=nickname,
        content=content.replace("\\n", "\n"),
    )


def _build_forward_nodes(bot: Bot, raw_text: str):
    lines = [line for line in (part.strip() for part in raw_text.splitlines()) if line]
    if not lines:
        raise ValueError("请至少提供一条节点内容")

    fallback_user_id = int(bot.self_id)
    nodes = []
    for index, line in enumerate(lines, start=1):
        node = _parse_forward_node(line, fallback_user_id + index)
        if node is not None:
            nodes.append(node)
    return nodes


# --- 核心解析逻辑 ---
async def parse_message_segments(bot: Bot, segments_data, depth: int = 0):
    indent = "  " * depth

    # 统一数据格式
    if isinstance(segments_data, Message):
        segments = segments_data
    elif isinstance(segments_data, dict):
        segments = Message([MessageSegment(segments_data['type'], segments_data['data'])])
    elif isinstance(segments_data, list):
        segments = Message(segments_data)
    else:
        segments = Message(str(segments_data))

    for seg in segments:
        if seg.type == "text":
            text = seg.data.get("text", "").strip()
            if text: print(f"{indent}[文字]: {text}")
        elif seg.type == "image":
            print(f"{indent}[图片]: {seg.data.get('url') or seg.data.get('file')}")
        elif seg.type == "json":
            print(f"{indent}[JSON卡片数据]")
        elif seg.type == "forward":
            res_id = seg.data.get("id")
            print(f"{indent}>>> 进入合并转发层级 (ID: {res_id})")
            try:
                forward_res = await bot.get_forward_msg(id=res_id)
                for node in forward_res.get("messages", []):
                    sender = node.get("sender", {}).get("nickname", "未知")
                    print(f"{indent} [{sender}]:")
                    await parse_message_segments(bot, node.get("message") or node.get("content"), depth + 1)
            except Exception as e:
                print(f"{indent}[错误]: 无法解析转发内容 - {e}")
            print(f"{indent}<<< 退出层级")


# --- 自动监听处理器 ---
monitor = on_message(priority=10, block=False)


@monitor.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if event.group_id == TARGET_GROUP_ID:
        print(f"\n{'=' * 20} 收到群消息 (ID: {event.message_id}) {'=' * 20}")
        await parse_message_segments(bot, event.message)


# --- 手动查询处理器 ---
search_cmd = on_command("查", permission=SUPERUSER, priority=5, block=False)


@search_cmd.handle()
async def _(bot: Bot, args: Message = CommandArg()):
    mid = args.extract_plain_text().strip()
    if mid.isdigit():
        # 调用上面封装好的函数
        try:
            msg_details = await bot.get_msg(message_id=int(mid))
            print(f"\n{'#' * 20} 查获消息预览 {'#' * 20}")
            await search_cmd.send(MessageSegment.text(f"{msg_details}"))
            print(f"{'#' * 50}\n")
        except Exception as e:
            await search_cmd.finish(f"ID {mid} 消息获取失败（可能由于消息太久已被服务器清理）{e}")


# --- 超管专用：伪造合并转发消息 ---
fake_forward_cmd = on_command("伪造合并转发", permission=SUPERUSER, priority=5, block=True)


@fake_forward_cmd.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    raw_text = arg.extract_plain_text().strip()
    if not raw_text:
        await fake_forward_cmd.finish(
            "用法:\n"
            "伪造合并转发\n"
            "昵称1|内容1\n"
            "昵称2|内容2|123456\n\n"
            "说明：每行一条节点，末尾可选填写 user_id。"
        )

    nodes = _build_forward_nodes(bot, raw_text)

    if isinstance(event, GroupMessageEvent):
        await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=nodes)
    else:
        await bot.call_api("send_private_forward_msg", user_id=event.user_id, messages=nodes)

    log.info(f"✅ 已发送 {len(nodes)} 条伪造合并转发节点")
