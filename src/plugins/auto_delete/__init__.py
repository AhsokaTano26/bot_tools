import asyncio
from nonebot import on_command, on_message, logger
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message

from .config import Config

# 内存存储：(group_id, user_id) 集合
auto_delete_users: set[tuple[int, int]] = set()

# 延迟撤回时间（秒）
DELETE_DELAY = 180


# --- 开启阅后即焚 ---
enable_cmd = on_command("开启阅后即焚", priority=10, block=True)


@enable_cmd.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    # 检查 bot 是否为群管理
    try:
        bot_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(bot.self_id), no_cache=True)
        if bot_info.get("role") not in ("admin", "owner"):
            await enable_cmd.finish("❌ 机器人不是群管理，无法开启阅后即焚")
    except Exception:
        await enable_cmd.finish("❌ 无法获取机器人权限信息")

    key = (event.group_id, event.user_id)
    auto_delete_users.add(key)
    await enable_cmd.finish(f"✅ 已开启阅后即焚，你的消息将在 {DELETE_DELAY // 60} 分钟后自动撤回")


# --- 关闭阅后即焚 ---
disable_cmd = on_command("关闭阅后即焚", priority=10, block=True)


@disable_cmd.handle()
async def _(event: GroupMessageEvent):
    key = (event.group_id, event.user_id)
    auto_delete_users.discard(key)
    await disable_cmd.finish("✅ 已关闭阅后即焚")


# --- 监听所有群消息 ---
msg_listener = on_message(priority=99, block=False)


@msg_listener.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    key = (event.group_id, event.user_id)
    if key not in auto_delete_users:
        return

    msg_id = event.message_id

    async def delayed_delete():
        await asyncio.sleep(DELETE_DELAY)
        try:
            await bot.delete_msg(message_id=msg_id)
            logger.info(f"阅后即焚: 已撤回消息 {msg_id}")
        except Exception as e:
            logger.debug(f"阅后即焚: 撤回消息 {msg_id} 失败 - {e}")

    asyncio.create_task(delayed_delete())
