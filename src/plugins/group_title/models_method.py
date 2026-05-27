import re
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import get_session
from .models import Member, Tag, GrouP, MemberTag, GroupSub


def validate_date(date_str: str) -> bool:
    """校验日期是否为合法的 MM-DD 格式"""
    if not re.match(r"^\d{2}-\d{2}$", date_str):
        return False
    month, day = int(date_str[:2]), int(date_str[3:])
    return 1 <= month <= 12 and 1 <= day <= 31


class DBManager:
    # --- 成员相关 ---
    @staticmethod
    async def add_member(name: str, date: str, extra: str = "") -> str:
        """添加成员，返回结果消息"""
        session = get_session()
        exists = await session.execute(select(Member).where(Member.name == name))
        if exists.scalar_one_or_none():
            return f"成员 [{name}] 已存在"
        session.add(Member(name=name, date=date, extra=extra))
        await session.commit()
        return "success"

    @staticmethod
    async def delete_member(name: str) -> bool:
        """删除成员及其关联关系"""
        session = get_session()
        result = await session.execute(select(Member).where(Member.name == name))
        member = result.scalar_one_or_none()
        if not member:
            return False
        await session.delete(member)
        await session.commit()
        return True

    @staticmethod
    async def update_member(name: str, new_name: str = None, new_date: str = None) -> str:
        """修改成员信息，返回结果消息"""
        session = get_session()
        result = await session.execute(select(Member).where(Member.name == name))
        member = result.scalar_one_or_none()
        if not member:
            return "成员不存在"
        if new_name:
            dup = await session.execute(select(Member).where(Member.name == new_name))
            if dup.scalar_one_or_none():
                return f"名字 [{new_name}] 已被占用"
            member.name = new_name
        if new_date:
            member.date = new_date
        await session.commit()
        return "success"

    @staticmethod
    async def batch_add_members(members: List[tuple]) -> tuple:
        """批量添加成员，返回 (新增名字列表, 更新名字列表, 已存在同日期名字列表)"""
        session = get_session()
        added = []
        updated = []
        skipped = []
        for name, date in members:
            result = await session.execute(select(Member).where(Member.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                if existing.date == date:
                    skipped.append(name)
                else:
                    existing.date = date
                    updated.append(name)
            else:
                session.add(Member(name=name, date=date))
                added.append(name)
        await session.commit()
        return added, updated, skipped

    @staticmethod
    async def get_members_by_date(date: str) -> List[Member]:
        session = get_session()
        stmt = select(Member).where(Member.date == date).options(selectinload(Member.tags))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- 标签相关 ---
    @staticmethod
    async def add_tag(name: str) -> bool:
        session = get_session()
        exists = await session.execute(select(Tag).where(Tag.name == name))
        if exists.scalar_one_or_none():
            return False
        session.add(Tag(name=name))
        await session.commit()
        return True

    @staticmethod
    async def delete_tag(name: str) -> bool:
        """删除标签及其所有关联关系"""
        session = get_session()
        result = await session.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            return False
        await session.delete(tag)
        await session.commit()
        return True

    @staticmethod
    async def bind_member_tag(member_name: str, tag_name: str) -> str:
        session = get_session()
        m_res = await session.execute(
            select(Member).where(Member.name == member_name).options(selectinload(Member.tags))
        )
        t_res = await session.execute(select(Tag).where(Tag.name == tag_name))
        m, t = m_res.scalar_one_or_none(), t_res.scalar_one_or_none()

        if not m or not t: return "成员或标签不存在"
        if t in m.tags: return "已存在关联"

        m.tags.append(t)
        await session.commit()
        return "success"

    @staticmethod
    async def batch_bind_member_tag(member_names: List[str], tag_name: str) -> tuple:
        """批量关联成员与标签，返回 (成功列表, 已存在列表, 不存在列表)"""
        session = get_session()
        t_res = await session.execute(select(Tag).where(Tag.name == tag_name))
        tag = t_res.scalar_one_or_none()
        if not tag:
            return [], [], member_names  # 标签不存在，全部标记为不存在

        bound = []
        already = []
        not_found = []
        for name in member_names:
            m_res = await session.execute(
                select(Member).where(Member.name == name).options(selectinload(Member.tags))
            )
            member = m_res.scalar_one_or_none()
            if not member:
                not_found.append(name)
            elif tag in member.tags:
                already.append(name)
            else:
                member.tags.append(tag)
                bound.append(name)
        await session.commit()
        return bound, already, not_found

    @staticmethod
    async def unbind_member_tag(member_name: str, tag_name: str) -> str:
        """取消成员与标签的关联"""
        session = get_session()
        m_res = await session.execute(
            select(Member).where(Member.name == member_name).options(selectinload(Member.tags))
        )
        t_res = await session.execute(select(Tag).where(Tag.name == tag_name))
        m, t = m_res.scalar_one_or_none(), t_res.scalar_one_or_none()

        if not m or not t:
            return "成员或标签不存在"
        if t not in m.tags:
            return "该成员未关联此标签"

        m.tags.remove(t)
        await session.commit()
        return "success"

    @staticmethod
    async def get_all_tags() -> List[Tag]:
        session = get_session()
        stmt = select(Tag)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    # --- 群组订阅相关 ---
    @staticmethod
    async def subscribe_group_tag(group_id: int, group_name: str, tag_name: str, bir_type: int) -> str:
        session = get_session()

        # 1. 检查标签
        t_res = await session.execute(select(Tag).where(Tag.name == tag_name))
        tag = t_res.scalar_one_or_none()
        if not tag: return "标签不存在"

        # 2. 获取或创建群组
        group = await session.get(GrouP, group_id)
        if not group:
            group = GrouP(
                group_id=group_id,
                group_name=group_name,
                birthday_type=bir_type
            )
            session.add(group)
        else:
            group.group_name = group_name
            group.birthday_type = bir_type

        await session.flush()

        # 3. 关联订阅
        stmt = (
            select(GrouP)
            .where(GrouP.group_id == group_id)
            .options(selectinload(GrouP.subscribed_tags))
        )
        result = await session.execute(stmt)
        group_obj = result.scalar_one()

        if tag in group_obj.subscribed_tags:
            return "已经订阅过了"

        group_obj.subscribed_tags.append(tag)
        await session.commit()
        return "success"

    @staticmethod
    async def unsubscribe_group_tag(group_id: int, tag_name: str) -> str:
        """取消群组对某标签的订阅"""
        session = get_session()
        t_res = await session.execute(select(Tag).where(Tag.name == tag_name))
        tag = t_res.scalar_one_or_none()
        if not tag:
            return "标签不存在"

        stmt = (
            select(GrouP)
            .where(GrouP.group_id == group_id)
            .options(selectinload(GrouP.subscribed_tags))
        )
        result = await session.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            return "该群未订阅任何标签"
        if tag not in group.subscribed_tags:
            return "该群未订阅此标签"

        group.subscribed_tags.remove(tag)
        # 如果没有任何订阅了，删除群组记录
        if not group.subscribed_tags:
            await session.delete(group)
        await session.commit()
        return "success"

    @staticmethod
    async def get_all_members(month: Optional[str] = None) -> List[Member]:
        session = get_session()
        stmt = select(Member).options(selectinload(Member.tags))
        if month:
            stmt = stmt.where(Member.date.like(f"{month}-%"))
        stmt = stmt.order_by(Member.date)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_subscribed_group_objects_by_tags(tag_ids: List[int]) -> List[GrouP]:
        """获取所有订阅了指定标签的群组完整对象"""
        session = get_session()
        stmt = (
            select(GrouP)
            .join(GroupSub)
            .where(GroupSub.tag_id.in_(tag_ids))
            .options(selectinload(GrouP.subscribed_tags))
            .distinct()
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_groups() -> List[GrouP]:
        session = get_session()
        stmt = select(GrouP).options(selectinload(GrouP.subscribed_tags))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_group_name(group_id: int, new_name: str) -> bool:
        session = get_session()
        group = await session.get(GrouP, group_id)
        if not group:
            return False
        group.group_name = new_name
        await session.commit()
        return True
