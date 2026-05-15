from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.permission import SUPERUSER

# 注册指令，建议权限设置为管理员或超级用户，防止刷屏
get_list = on_command("获取成员列表", permission=SUPERUSER, priority=5, block=True)


@get_list.handle()
async def handle_get_list(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id

    try:
        # 获取群成员列表
        member_list = await bot.get_group_member_list(group_id=group_id)

        result_text = f"📢 群号 {group_id} 成员清单：\n"

        for member in member_list:
            user_id = member['user_id']
            # 优先获取群名片，如果没有名片则取昵称
            nickname = member['card'] if member['card'] else member['nickname']
            result_text += f"🔹 {nickname} ({user_id})\n"

        # 考虑到群成员较多时可能触发风控，建议只发送前 100 条或分段发送
        # 这里直接通过分段消息或长文本发送
        print(result_text.strip())

    except Exception as e:
        await get_list.finish(f"❌ 获取失败：{str(e)}")