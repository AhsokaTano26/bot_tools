from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent
from nonebot.permission import SUPERUSER
from nonebot.log import logger

# 建议仅限超级管理员触发，避免信息泄露
get_groups = on_command("检查群聊", permission=SUPERUSER, priority=10, block=True)


@get_groups.handle()
async def handle_get_groups(bot: Bot, event: MessageEvent):
    try:
        # 调用 OneBot V11 API 获取群列表
        group_list = await bot.get_group_list()

        if not group_list:
            await get_groups.finish("当前 Bot 未加入任何群聊，或 NapCat 尚未加载完毕。")

        # 提取群号和群名称
        # 这里的 "正常" 逻辑通常指能获取到基本信息且未被封禁
        active_groups = []
        for group in group_list:
            group_id = group['group_id']
            group_name = group.get('group_name', '未知群名')
            member_count = group.get('member_count', 0)

            active_groups.append(f"• {group_name} ({group_id}) - {member_count}人")

        # 组装消息
        summary = f"📊 Bot 当前在 {len(active_groups)} 个群聊中：\n" + "\n".join(active_groups)

        await get_groups.send(summary)

    except Exception as e:
        logger.error(f"获取群列表失败: {e}")
        await get_groups.finish(f"❌ 获取失败，请检查 NapCat 日志。")