from nonebot import get_plugin_config, on_command, require, get_bot
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.adapters import Event
from nonebot_plugin_orm import get_session
from nonebot.log import logger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from .config import Config
from .models_method import BanGManger, GrouPManger
from .models import BanG, GrouP

__plugin_meta__ = PluginMetadata(
    name="group_title",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)
scheduler = require("nonebot_plugin_apscheduler").scheduler


modify_nickname = on_command("修改群昵称", aliases={"setcard"}, priority=5)


@modify_nickname.handle()
async def handle_set_card(bot: Bot, event: Event):
    """
    处理修改群昵称的命令。

    参数:
        bot: NoneBot Bot 对象
        event: 接收到的事件对象，包含 message 属性
    """

    try:
        group_id = event.group_id
    except ValueError:
        await modify_nickname.finish("❌ 群号必须是数字。")

    try:
        group_info = await bot.get_group_info(
            group_id=group_id,  # 目标群的群号
        )
        print(group_info)
        await modify_nickname.send(f"✅ 成功{group_info}")
    except Exception as e:
        await modify_nickname.finish(f"❌ 失败：{e}")

@scheduler.scheduled_job(CronTrigger(hour=23, minute=0))
async def auto_send_msg_func():
    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"获取在线bot错误：{e}")
    async with get_session() as db_session:
        now = datetime.now()
        formatted_datetime = now.strftime("%m-%d")
        bir_msg = await BanGManger.get_Sign_by_student_id(db_session,formatted_datetime)
        if bir_msg:
            name = bir_msg.name
            extra = bir_msg.extra
            group_list = await GrouPManger.get_all_student_id(db_session)
            for group in group_list:
                group_id = group.group_id
                group_name = group.group_name
                bir_name = group.birthday_name

                birth_name = f"{group_name}({name}{bir_name})"
                try:
                    await bot.set_group_name(
                        group_id=group_id,  # 目标群的群号
                        group_name=birth_name  # 新的群昵称
                    )
                    logger.info(f"✅ 成功尝试将群 {group_id} 的群昵称修改为：{birth_name}")
                except Exception as e:
                    logger.error(f"❌ 修改群昵称失败，请检查机器人权限或群号是否正确。\n错误信息：{e}")
        elif bir_msg is None:
            group_list = await GrouPManger.get_all_student_id(db_session)
            for group in group_list:
                group_id = group.group_id
                group_name = group.group_name
                try:
                    group_info = await bot.get_group_info(group_id=group_id)
                    logger.info(f"✅ 成功获取群 {group_id} 的群信息")
                except Exception as e:
                    logger.error(f"❌ 修改群信息失败：{e}")
                if group_info.group_name != group_name:
                    try:
                        await bot.set_group_name(
                            group_id=group_id,  # 目标群的群号
                            group_name=group_name  # 新的群昵称
                        )
                        logger.info(f"✅ 成功尝试将群 {group_id} 的群昵称修改为：{group_name}")
                    except Exception as e:
                        logger.error(f"❌ 修改群昵称失败，请检查机器人权限或群号是否正确。\n错误信息：{e}")
        else:
            logger.error("未知异常")
