from datetime import datetime, timedelta
from nonebot import get_bot, on_command, require, logger
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, MessageSegment, Message
from nonebot.permission import SUPERUSER

# 确保定时任务插件已加载
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 导入业务方法和模型
from .models_method import DBManager, validate_date
from .models import Tag, GrouP
from .str_type import StrType


# --- 辅助函数 ---

async def get_group_name(group_id: int) -> str:
    try:
        bot = get_bot()
        group_info = await bot.get_group_info(group_id=group_id, no_cache=False)
        return group_info.get("group_name", "未知群聊")
    except Exception as e:
        logger.error(f"获取群 {group_id} 信息失败: {e}")
        return "未知群聊"


def is_admin_or_superuser(event: GroupMessageEvent) -> bool:
    return event.sender.role in ["admin", "owner"] or str(event.user_id) in event.bot.config.superusers


# --- 1. 定时任务：每天 23:00 修改名片 ---

@scheduler.scheduled_job("cron", hour=23, minute=00, id="birthday_remind")
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
        logger.info(f"日期 {tomorrow} 没有成员过生日，恢复群名")
        groups = await DBManager.get_all_groups()
        for group in groups:
            try:
                current_info = await bot.get_group_info(group_id=int(group.group_id), no_cache=False)
                current_name = current_info.get("group_name", "")
                if current_name != group.group_name:
                    await bot.set_group_name(
                        group_id=int(group.group_id),
                        group_name=group.group_name
                    )
                    logger.info(f"群 {group.group_id} 群名已恢复为: {group.group_name}")
            except Exception as e:
                logger.error(f"恢复群 {group.group_id} 群名失败: {e}")
        return

    # 2. 聚合所有生日成员的名字（限制长度防止群名超限）
    all_names = [m.name for m in members]
    all_birthday_names = "&".join(all_names)
    # QQ 群名限制约 60 字符，预留空间给模板文字
    if len(all_birthday_names) > 30:
        all_birthday_names = "&".join(all_names[:3]) + f"等{len(all_names)}人"

    # 3. 收集所有相关的标签 ID，用于查找订阅群组
    all_tag_ids = []
    for m in members:
        all_tag_ids.extend([t.id for t in m.tags])

    if not all_tag_ids:
        logger.warning(f"日期 {tomorrow} 有生日成员 {[m.name for m in members]} 但未关联任何标签，跳过提醒")
        return

    # 4. 获取所有订阅了这些标签的群组对象
    groups = await DBManager.get_subscribed_group_objects_by_tags(list(set(all_tag_ids)))

    for group in groups:
        try:
            new_name = StrType.type(
                group_name=group.group_name,
                name=all_birthday_names,
                bir_type=group.birthday_type
            )
            await bot.set_group_name(
                group_id=int(group.group_id),
                group_name=new_name
            )
            logger.info(f"群 {group.group_id} 名片已更新为: {new_name}")
        except Exception as e:
            logger.error(f"更新群 {group.group_id} 名片失败: {e}")


# --- 2. 指令交互部分 ---

# 增加成员 (超管)
add_mem = on_command("增加成员", permission=SUPERUSER, priority=10, block=True)


@add_mem.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await add_mem.finish("用法: 增加成员 名字 MM-DD [备注]")

    name, date = args[0], args[1]
    if not validate_date(date):
        await add_mem.finish("⚠️ 日期格式错误，应为 MM-DD（如 01-15）")

    extra = args[2] if len(args) > 2 else ""
    result = await DBManager.add_member(name, date, extra)
    if result == "success":
        await add_mem.finish(f"✅ 成功录入成员: {name}")
    else:
        await add_mem.finish(f"❌ {result}")


# 批量导入成员 (超管)
batch_add_mem = on_command("批量导入", permission=SUPERUSER, priority=10, block=True)


@batch_add_mem.handle()
async def _(arg: Message = CommandArg()):
    text = arg.extract_plain_text().strip()
    if not text:
        await batch_add_mem.finish("用法: 批量导入 名字1 MM-DD, 名字2 MM-DD, ...")

    members = []
    invalid_dates = []
    for item in text.split(","):
        parts = item.strip().split()
        if len(parts) < 2:
            continue
        name, date = parts[0], parts[1]
        if not validate_date(date):
            invalid_dates.append(f"{name}({date})")
            continue
        members.append((name, date))

    if invalid_dates:
        await batch_add_mem.finish(f"⚠️ 以下日期格式错误，应为 MM-DD: {', '.join(invalid_dates)}")

    if not members:
        await batch_add_mem.finish("⚠️ 未解析到有效数据，请检查格式: 名字1 MM-DD, 名字2 MM-DD, ...")

    added, updated, skipped = await DBManager.batch_add_members(members)
    msg_parts = []
    if added:
        msg_parts.append(f"✅ 新增 {len(added)} 名成员: {', '.join(added)}")
    if updated:
        msg_parts.append(f"🔄 更新 {len(updated)} 名成员的生日日期: {', '.join(updated)}")
    if skipped:
        msg_parts.append(f"⚠️ 已存在且日期相同，已跳过 {len(skipped)} 人: {', '.join(skipped)}")
    if not msg_parts:
        msg_parts.append("⚠️ 无有效数据")
    await batch_add_mem.finish("\n".join(msg_parts))


# 删除成员 (超管)
del_mem = on_command("删除成员", permission=SUPERUSER, priority=10, block=True)


@del_mem.handle()
async def _(arg: Message = CommandArg()):
    name = arg.extract_plain_text().strip()
    if not name:
        await del_mem.finish("用法: 删除成员 名字")

    success = await DBManager.delete_member(name)
    if success:
        await del_mem.finish(f"✅ 已删除成员: {name}")
    else:
        await del_mem.finish(f"❌ 成员 [{name}] 不存在")


# 批量删除成员 (超管)
batch_del_mem = on_command("批量删除", permission=SUPERUSER, priority=10, block=True)


@batch_del_mem.handle()
async def _(arg: Message = CommandArg()):
    text = arg.extract_plain_text().strip()
    if not text:
        await batch_del_mem.finish("用法: 批量删除 成员1, 成员2, ...")

    names = [n.strip() for n in text.split(",") if n.strip()]
    if not names:
        await batch_del_mem.finish("⚠️ 未解析到有效成员名")

    deleted, not_found = await DBManager.batch_delete_members(names)

    msg_parts = []
    if deleted:
        msg_parts.append(f"✅ 已删除 {len(deleted)} 人: {', '.join(deleted)}")
    if not_found:
        msg_parts.append(f"❌ 未找到 {len(not_found)} 人: {', '.join(not_found)}")
    if not msg_parts:
        msg_parts.append("⚠️ 无有效数据")
    await batch_del_mem.finish("\n".join(msg_parts))


# 修改成员 (超管)
edit_mem = on_command("修改成员", permission=SUPERUSER, priority=10, block=True)


@edit_mem.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await edit_mem.finish("用法: 修改成员 原名字 新名字/新日期\n示例: 修改成员 张三 李四\n示例: 修改成员 张三 05-20")

    old_name = args[0]
    new_value = args[1]

    # 判断是否像日期格式 (XX-XX)
    if re.match(r"^\d{2}-\d{2}$", new_value):
        if not validate_date(new_value):
            await edit_mem.finish(f"⚠️ 无效日期: {new_value}，应为合法的 MM-DD 格式")
        res = await DBManager.update_member(old_name, new_date=new_value)
    else:
        res = await DBManager.update_member(old_name, new_name=new_value)

    if res == "success":
        await edit_mem.finish(f"✅ 成员 [{old_name}] 已更新")
    else:
        await edit_mem.finish(f"❌ {res}")


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


# 删除标签 (超管)
del_tag_cmd = on_command("删除标签", permission=SUPERUSER, priority=10, block=True)


@del_tag_cmd.handle()
async def _(arg: Message = CommandArg()):
    tag_name = arg.extract_plain_text().strip()
    if not tag_name:
        await del_tag_cmd.finish("用法: 删除标签 标签名")

    success = await DBManager.delete_tag(tag_name)
    if success:
        await del_tag_cmd.finish(f"✅ 标签 [{tag_name}] 已删除")
    else:
        await del_tag_cmd.finish(f"❌ 标签 [{tag_name}] 不存在")


# 关联成员与标签 (超管)
bind_tag = on_command("关联标签", permission=SUPERUSER, priority=10, block=True)


@bind_tag.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await bind_tag.finish("用法: 关联标签 成员名 标签名")

    res = await DBManager.bind_member_tag(args[0], args[1])
    await bind_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")


# 批量关联 (超管)
batch_bind_tag = on_command("批量关联", permission=SUPERUSER, priority=10, block=True)


@batch_bind_tag.handle()
async def _(arg: Message = CommandArg()):
    text = arg.extract_plain_text().strip()
    parts = text.split(None, 1)
    if len(parts) < 2:
        await batch_bind_tag.finish("用法: 批量关联 标签名 成员1, 成员2, ...\n用法: 批量关联 标签名 全部")

    tag_name = parts[0]
    second_part = parts[1].strip()

    # 支持 "全部" 关键字
    if second_part in ("全部", "*"):
        all_members = await DBManager.get_all_members()
        names = [m.name for m in all_members]
    else:
        names = [n.strip() for n in second_part.split(",") if n.strip()]

    if not names:
        await batch_bind_tag.finish("⚠️ 未解析到有效成员名")

    bound, already, not_found = await DBManager.batch_bind_member_tag(names, tag_name)

    msg_parts = []
    if bound:
        msg_parts.append(f"✅ 成功关联 {len(bound)} 人: {', '.join(bound)}")
    if already:
        msg_parts.append(f"⚠️ 已关联 {len(already)} 人: {', '.join(already)}")
    if not_found:
        msg_parts.append(f"❌ 未找到 {len(not_found)} 人: {', '.join(not_found)}")
    if not msg_parts:
        msg_parts.append("⚠️ 无有效数据")
    await batch_bind_tag.finish("\n".join(msg_parts))


# 取消关联 (超管)
unbind_tag = on_command("取消关联", permission=SUPERUSER, priority=10, block=True)


@unbind_tag.handle()
async def _(arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if len(args) < 2:
        await unbind_tag.finish("用法: 取消关联 成员名 标签名")

    res = await DBManager.unbind_member_tag(args[0], args[1])
    await unbind_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")


# 批量取消关联 (超管)
batch_unbind_tag = on_command("批量取消关联", permission=SUPERUSER, priority=10, block=True)


@batch_unbind_tag.handle()
async def _(arg: Message = CommandArg()):
    text = arg.extract_plain_text().strip()
    parts = text.split(None, 1)
    if len(parts) < 2:
        await batch_unbind_tag.finish("用法: 批量取消关联 标签名 成员1, 成员2, ...")

    tag_name = parts[0]
    names = [n.strip() for n in parts[1].split(",") if n.strip()]
    if not names:
        await batch_unbind_tag.finish("⚠️ 未解析到有效成员名")

    unbound, not_bound, not_found = await DBManager.batch_unbind_member_tag(names, tag_name)

    msg_parts = []
    if unbound:
        msg_parts.append(f"✅ 已取消关联 {len(unbound)} 人: {', '.join(unbound)}")
    if not_bound:
        msg_parts.append(f"⚠️ 未关联此标签 {len(not_bound)} 人: {', '.join(not_bound)}")
    if not_found:
        msg_parts.append(f"❌ 未找到 {len(not_found)} 人: {', '.join(not_found)}")
    if not msg_parts:
        msg_parts.append("⚠️ 无有效数据")
    await batch_unbind_tag.finish("\n".join(msg_parts))


# 订阅标签 (群管/超管)
sub_tag = on_command("订阅标签", priority=10, block=True)


@sub_tag.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    if not is_admin_or_superuser(event):
        await sub_tag.finish("❌ 只有群管理或超管可以执行此操作")

    msg = arg.extract_plain_text().strip().split()
    if len(msg) < 2:
        await sub_tag.finish("⚠️ 用法: 订阅标签 [标签名] [提醒类型1-3]")

    tag_name = msg[0]
    try:
        bir_type = int(msg[1])
    except ValueError:
        await sub_tag.finish("⚠️ 提醒类型必须是数字 (1, 2 或 3)")

    if bir_type not in (1, 2, 3):
        await sub_tag.finish("⚠️ 提醒类型必须是 1、2 或 3")

    group_info = await bot.get_group_info(group_id=event.group_id)
    group_name = group_info.get("group_name", "未知群聊")

    res = await DBManager.subscribe_group_tag(
        group_id=event.group_id,
        group_name=group_name,
        tag_name=tag_name,
        bir_type=bir_type
    )

    await sub_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")


# 取消订阅 (群管/超管)
unsub_tag = on_command("取消订阅", priority=10, block=True)


@unsub_tag.handle()
async def _(event: GroupMessageEvent, arg: Message = CommandArg()):
    if not is_admin_or_superuser(event):
        await unsub_tag.finish("❌ 只有群管理或超管可以执行此操作")

    tag_name = arg.extract_plain_text().strip()
    if not tag_name:
        await unsub_tag.finish("用法: 取消订阅 标签名")

    res = await DBManager.unsubscribe_group_tag(event.group_id, tag_name)
    await unsub_tag.finish(f"{'✅' if res == 'success' else '❌'} {res}")


# 修改标准群名 (群管/超管)
update_group_name_cmd = on_command("修改标准群名", priority=10, block=True)


@update_group_name_cmd.handle()
async def _(event: GroupMessageEvent, arg: Message = CommandArg()):
    if not is_admin_or_superuser(event):
        await update_group_name_cmd.finish("❌ 只有群管理或超管可以执行此操作")

    new_name = arg.extract_plain_text().strip()
    if not new_name:
        await update_group_name_cmd.finish("⚠️ 用法: 修改标准群名 [新名称]")

    success = await DBManager.update_group_name(event.group_id, new_name)
    if success:
        await update_group_name_cmd.finish(f"✅ 标准群名已更新为: {new_name}")
    else:
        await update_group_name_cmd.finish("❌ 该群尚未订阅任何标签，请先使用 [订阅标签] 指令")


# help 指令
help_msg = on_command("help", priority=10, block=True)


@help_msg.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    help_content = '''
🎂 BanG Dream 生日提醒助手帮助
---------------------------
🔹 [用户指令]
订阅标签 [标签名] [提醒类型1-3] - (群管) 为本群订阅生日推送
取消订阅 [标签名] - (群管) 取消本群对某标签的订阅
修改标准群名 [新名称] - (群管) 修改数据库中存储的标准群名

可选生日类型如下：
1: "{group_name}🎉@{name}生日快乐🎉"
2: "{group_name}(@{name}生日快乐!)"
3: "{group_name}(@{name}生日快乐🎂)"

查看成员 [月份] - 查看全量或特定月份生日成员
---------------------------
🔸 [超管指令]
增加成员 名字 MM-DD [备注] - 录入新成员
删除成员 名字 - 删除指定成员
修改成员 原名字 新名字/新日期 - 修改成员名字或生日
批量导入 名字1 MM-DD, 名字2 MM-DD, ... - 批量导入成员
批量删除 名字1, 名字2, ... - 批量删除成员
增加标签 [标签名] - 创建新分类
删除标签 [标签名] - 删除指定分类
关联标签 [名字] [标签] - 手动绑定成员与标签
批量关联 [标签] 名字1, 名字2, ... - 批量绑定成员与标签
批量关联 [标签] 全部 - 为所有成员绑定标签
取消关联 [名字] [标签] - 取消成员与标签的关联
批量取消关联 [标签] 名字1, 名字2, ... - 批量取消关联
查看标签 - 列出库中所有标签
查看订阅 - 查看全量群组订阅详情
'''

    nodes = []
    nodes.append(
        MessageSegment.node_custom(
            user_id=int(bot.self_id),
            nickname="BanG Dream 生日助手",
            content=help_content))

    if isinstance(event, GroupMessageEvent):
        await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=nodes)
    else:
        await bot.call_api("send_private_forward_msg", user_id=event.user_id, messages=nodes)


### 3. 超管专用：查看指令 ---

# 查看订阅 (仅超管)
view_subs = on_command("查看订阅", permission=SUPERUSER, priority=10, block=True)


@view_subs.handle()
async def _():
    groups = await DBManager.get_all_groups()

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


# 查看成员 (任何人)
view_members = on_command("查看成员", priority=10, block=True)


@view_members.handle()
async def _(arg: Message = CommandArg()):
    month = arg.extract_plain_text().strip()
    if month.isdigit():
        month_int = int(month)
        if month_int < 1 or month_int > 12:
            await view_members.finish("⚠️ 月份应为 1-12")
        month = f"{month_int:02d}"
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

    full_msg = header + "\n".join(lines)

    if len(full_msg) > 1500:
        await view_members.finish("⚠️ 数据量较大，请使用 '查看成员 [月份]' 按月筛选")

    await view_members.finish(full_msg)
