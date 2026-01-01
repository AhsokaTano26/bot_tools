from nonebot import get_plugin_config, on_command, require, get_bot
from nonebot.adapters.onebot.v11 import GROUP_OWNER, GROUP_ADMIN, Message
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot_plugin_orm import get_session
from nonebot.log import logger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError

from .config import Config
from .models_method import BanGManger, GrouPManger
from .models import BanG, GrouP
from .str_type import StrType

__plugin_meta__ = PluginMetadata(
    name="group_title",
    description="本插件用于根据角色生日数据库，在角色生日时修改QQ群昵称",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)
scheduler = require("nonebot_plugin_apscheduler").scheduler

birthday = on_command("birthday", priority=10, permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN)

@birthday.handle()
async def handle_birthday(args: Message = CommandArg()):
    command = args.extract_plain_text().strip()

    try:
        type = str(command.split(" ")[0])
        group_id = int(command.split(" ")[1])
        group_name = str(command.split(" ")[2])
        bir_type = str(command.split(" ")[3])
    except Exception as e:
        await birthday.finish("命令格式错误")

    if type == "创建群组":
        async with (get_session() as db_session):
            try:
                # 检查数据库中是否已存在该 Student_id 的记录
                existing_lanmsg = await GrouPManger.get_Sign_by_student_id(
                    db_session, group_id)
                if existing_lanmsg:  # 更新记录
                    logger.info(f"群{group_id}已存在")
                    await birthday.send(f"群{group_id}已存在")
                else:
                    try:
                        # 写入数据库
                        await GrouPManger.create_signmsg(
                            db_session,
                            group_id=group_id,
                            group_name=group_name,
                            birthday_type=bir_type,
                        )
                        await birthday.send(
                            f"✅ 创建成功\n"
                            f"群组名: {group_name}\n"
                            f"群号: {group_id}\n"
                        )
                    except Exception as e:
                        logger.opt(exception=False).error(f"创建群{group_id}时发生错误: {e}")
            except SQLAlchemyError as e:
                logger.opt(exception=False).error(f"数据库操作错误: {e}")

    elif type == "删除群组":
        async with (get_session() as db_session):
            try:
                # 检查数据库中是否已存在该 Student_id 的记录
                existing_lanmsg = await GrouPManger.get_Sign_by_student_id(
                    db_session, group_id)
                if not existing_lanmsg:  # 更新记录
                    logger.info(f"群{group_id}的订阅不存在")
                    await birthday.send(f"群{group_id}的订阅不存在")
                else:
                    try:
                        # 写入数据库
                        await GrouPManger.delete_id(db_session, id=group_id)
                        await birthday.send(
                            f"✅ 订阅取消成功\n"
                            f"群组名: {group_name}\n"
                            f"群号: {group_id}\n"
                        )
                    except Exception as e:
                        logger.opt(exception=False).error(f"取消群{group_id}的订阅时发生错误: {e}")
            except SQLAlchemyError as e:
                logger.opt(exception=False).error(f"数据库操作错误: {e}")
    else:
        logger.opt(exception=False).error("命令格式错误")
        await birthday.finish("命令格式错误")



@scheduler.scheduled_job(CronTrigger(hour=23, minute=00))
async def auto_send_msg_func():
    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"获取在线bot错误：{e}")
    async with get_session() as db_session:
        now = datetime.now()
        next_day = now + timedelta(days=1)
        formatted_datetime = next_day.strftime("%m-%d")
        bir_msg = await BanGManger.get_Sign_by_student_id(db_session,formatted_datetime)

        if bir_msg:
            name = bir_msg.name
            extra = bir_msg.extra
            group_list = await GrouPManger.get_all_student_id(db_session)
            for group in group_list:
                groupmsg = await GrouPManger.get_Sign_by_student_id(db_session, group)
                group_id = groupmsg.group_id

                birth_name = StrType().type(
                    name=name,
                    group_name=groupmsg.group_name,
                    bir_type=groupmsg.birthday_type,
                )

                try:
                    await bot.set_group_name(
                        group_id=group_id,  # 目标群的群号
                        group_name=birth_name  # 新的群昵称
                    )
                    logger.info(f"✅ 成功尝试将群 {group_id} 的群昵称修改为：{birth_name}")
                except Exception as e:
                    logger.error(f"❌ 修改群昵称失败，请检查机器人权限或群号是否正确。\n错误信息：{e}")

                if extra:
                    try:
                        await bot.send_group_msg(
                            group_id=group_id,
                            message=extra,
                        )
                        logger.info(f"成功向群 {group_id} 发送信息")
                    except Exception as e:
                        logger.error(f"错误信息：{e}")

        elif bir_msg is None:
            group_list = await GrouPManger.get_all_student_id(db_session)
            for group in group_list:
                groupmsg = await GrouPManger.get_Sign_by_student_id(db_session, group)
                group_id = groupmsg.group_id
                group_name = groupmsg.group_name
                try:
                    group_info = await bot.get_group_info(group_id=group_id)
                    logger.info(f"✅ 成功获取群 {group_id} 的群信息")
                except Exception as e:
                    logger.error(f"❌ 获取群信息失败：{e}")
                if group_info['group_name'] != group_name:
                    try:
                        await bot.set_group_name(
                            group_id=group_id,
                            group_name=group_name
                        )
                        logger.info(f"✅ 成功尝试将群 {group_id} 的群昵称修改为：{group_name}")
                    except Exception as e:
                        logger.error(f"❌ 修改群昵称失败，请检查机器人权限或群号是否正确。\n错误信息：{e}")
        else:
            logger.error("未知异常")
