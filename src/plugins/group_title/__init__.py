from datetime import datetime, timedelta
from nonebot import get_bot, on_command, require, logger
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, MessageSegment ,Message
from nonebot.permission import SUPERUSER

# 确保定时任务插件已加载
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 导入你的业务方法和模型
from .models_method import DBManager
from .models import Tag, GrouP
from .str_type import StrType


# --- 1. 定时任务：每天 23:00 修改名片 ---

@scheduler.scheduled_job("cron", hour=23, minute=0, id="birthday_remind")
async def birthday_remind():
    try:
        bot = get_bot()
    except ValueError:
        logger.warning("未找到有效 Bot 实例，跳过定时任务")
        return

    # 1. 获取明天的日期
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%m-%d")
    members = await DBManager.get_members_by_date(tomorrow)

    if not members:
        logger.info(f"日期 {tomorrow} 没有成员过生日，跳过任务。")
        return

    # 2. 聚合所有生日成员的名字
    # 结果示例: "和奏瑞依&Raychell&三泽纱千香"
    all_birthday_names = "&".join([m.name for m in members])

    # 3. 收集所有相关的标签 ID，用于查找订阅群组
    all_tag_ids = []
    for m in members:
        all_tag_ids.extend([t.id for t in m.tags])

    if not all_tag_ids:
        return

    # 4. 获取所有订阅了这些标签的群组对象
    groups = await DBManager.get_subscribed_group_objects_by_tags(list(set(all_tag_ids)))

    for group in groups:
        try:
            # 5. 根据 StrType 获取格式化后的新名片
            # group.group_name: 数据库存的群名
            # all_birthday_names: 聚合后的名字
            # group.birthday_type: 数据库存的 1, 2, 3 类型
            new_card = StrType.type(
                group_name=group.group_name,
                name=all_birthday_names,
                bir_type=group.birthday_type
            )

            # 6. 执行名片修改
            await bot.set_group_card(
                group_id=int(group.group_id),
                user_id=int(bot.self_id),
                card=new_card
            )
            logger.info(f"群 {group.group_id} 名片已更新为: {new_card}")

        except Exception as e:
            logger.error(f"更新群 {group.group_id} 名片失败: {e}")


### 2. 指令交互部分 ---

# 增加成员 (超管)
add_mem = on_command("增加成员", permission=SUPERUSER, priority=10, block=True)


@add_mem.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await add_mem.finish("用法: 增加成员 名字 MM-DD [备注]")

    name, date = args[0], args[1]
    extra = args[2] if len(args) > 2 else ""
    await DBManager.add_member(name, date, extra)
    await add_mem.finish(f"✅ 成功录入成员: {name}")


# 增加标签 (超管)
add_tag_cmd = on_command("增加标签", permission=SUPERUSER, priority=10, block=True)


@add_tag_cmd.handle()
async def _(arg: Message = CommandArg()):
    tag_name = arg.extract_plain_text().strip()
    if not tag_name:
        await add_tag_cmd.finish("用法: 增加标签 标签名")

    success = await DBManager.add_tag(tag_name)
    msg = f"✅ 标签 [{tag_name}] 已创建" if success else f"❌ 标签 [{tag_name}] 已存在"
    await add_tag_cmd.finish(msg)


# 关联成员与标签 (超管)
bind_tag = on_command("关联标签", permission=SUPERUSER, priority=10, block=True)


@bind_tag.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await bind_tag.finish("用法: 关联标签 成员名 标签名")

    res = await DBManager.bind_member_tag(args[0], args[1])
    await bind_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")


# 订阅标签 (群管/超管)
sub_tag = on_command("订阅标签", priority=10, block=True)


@sub_tag.handle()
async def _(event: GroupMessageEvent, arg: Message = CommandArg()):
    # 简单的群权限校验
    if event.sender.role not in ["admin", "owner"] and str(event.user_id) not in event.bot.config.superusers:
        await sub_tag.finish("❌ 只有群管理或超管可以执行此操作")

    tag_name = arg.extract_plain_text().strip()
    if not tag_name:
        await sub_tag.finish("用法: 订阅标签 标签名")

    res = await DBManager.subscribe_group_tag(event.group_id, tag_name)
    await sub_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")

help_msg = on_command("help", priority=10, block=True)


@help_msg.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    # 1. 定义帮助内容
    help_content = [
        "🎂 BanG Dream 生日提醒助手助手帮助",
        "---------------------------",
        "🔹 [用户指令]",
        "订阅标签 [标签名] - (群管) 为本群订阅生日推送",
        "---------------------------",
        "🔸 [超管指令]",
        "增加成员 名字 MM-DD [备注] - 录入新成员",
        "增加标签 [标签名] - 创建新分类",
        "关联标签 [名字] [标签] - 手动绑定成员与标签",
        "查看标签 - 列出库中所有标签",
        "查看订阅 - 查看全量群组订阅详情",
        "查看成员 [月份] - 查看全量或特定月份生日成员",
    ]

    # 2. 构造合并转发节点
    # 每个节点代表一条聊天记录
    nodes = []
    for line in help_content:
        nodes.append(
            MessageSegment.node_custom(
                user_id=int(bot.self_id),
                nickname="BanG Dream 生日助手",
                content=line
            )
        )

    # 3. 发送合并转发消息
    # 注意：在群聊中发送和私聊中发送的 API 略有不同
    if isinstance(event, GroupMessageEvent):
        await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=nodes)
    else:
        # 私聊环境
        await bot.call_api("send_private_forward_msg", user_id=event.user_id, messages=nodes)

### 3. 超管专用：查看所有订阅情况 ---

# 查看订阅 (仅超管)
view_subs = on_command("查看订阅", permission=SUPERUSER, priority=10, block=True)


@view_subs.handle()
async def _():
    # 我们需要在 DBManager 中补一个获取全量订阅的方法，或者直接在这里查询
    from .models_method import async_scoped_session
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select

    # 直接查询所有有订阅关系的群
    stmt = select(GrouP).options(selectinload(GrouP.subscribed_tags))
    result = await async_scoped_session.execute(stmt)
    groups = result.scalars().all()

    if not groups:
        await view_subs.finish("目前没有任何群组订阅标签。")

    msg = "📊 当前全量订阅清单：\n"
    for g in groups:
        tags = [t.name for t in g.subscribed_tags]
        if tags:
            msg += f"\n群 {g.group_id}: {', '.join(tags)}"

    await view_subs.finish(msg.strip())



# 查看所有标签 (仅超管)
view_tags = on_command("查看标签", permission=SUPERUSER, priority=10, block=True)


@view_tags.handle()
async def _():
    tags = await DBManager.get_all_tags()
    if not tags:
        await view_tags.finish("🏷️ 数据库中暂无标签。")

    tag_list = [t.name for t in tags]
    msg = f"🔖 当前所有标签：\n{', '.join(tag_list)}"
    await view_tags.finish(msg)


# 查看成员 (仅超管)
view_members = on_command("查看成员", permission=SUPERUSER, priority=10, block=True)


@view_members.handle()
async def _(arg: Message = CommandArg()):
    month = arg.extract_plain_text().strip()
    # 如果用户输入了数字，补全为 MM 格式
    if month.isdigit():
        month = f"{int(month):02d}"
    else:
        month = None

    members = await DBManager.get_all_members(month)

    if not members:
        await view_members.finish(f"👥 {'该月份' if month else ''}暂无成员数据。")

    header = f"🎂 {'月份: ' + month if month else '全量'}成员名单：\n"
    lines = []
    for m in members:
        tags = [t.name for t in m.tags]
        tag_str = f" [{'/'.join(tags)}]" if tags else ""
        lines.append(f"{m.date} {m.name}{tag_str}")

    # 如果全量查看且人数过多，NoneBot 可能会截断，建议分段或按月查看
    full_msg = header + "\n".join(lines)

    # 简单的分段处理，防止消息过长
    if len(full_msg) > 1500:
        await view_members.send("⚠️ 数据量较大，建议使用 '查看成员 [月份]' 筛选")

    await view_members.finish(full_msg)