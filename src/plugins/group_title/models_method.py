from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import async_scoped_session  # 导入作用域会话
from .models import Member, Tag, GrouP, MemberTag, GroupSub


class DBManager:
    # --- 成员相关 ---
    @staticmethod
    async def add_member(name: str, date: str, extra: str = "") -> bool:
        # 直接使用 async_scoped_session，它在当前 context 下是唯一的
        new_m = Member(name=name, date=date, extra=extra)
        async_scoped_session.add(new_m)
        await async_scoped_session.commit()
        return True

    @staticmethod
    async def get_members_by_date(date: str) -> List[Member]:
        # 注意：使用 scoped_session 时，查询方式依然一致
        stmt = select(Member).where(Member.date == date).options(selectinload(Member.tags))
        result = await async_scoped_session.execute(stmt)
        return list(result.scalars().all())

    # --- 标签相关 ---
    @staticmethod
    async def add_tag(name: str) -> bool:
        exists = await async_scoped_session.execute(select(Tag).where(Tag.name == name))
        if exists.scalar_one_or_none():
            return False
        async_scoped_session.add(Tag(name=name))
        await async_scoped_session.commit()
        return True

    @staticmethod
    async def bind_member_tag(member_name: str, tag_name: str) -> str:
        m_res = await async_scoped_session.execute(
            select(Member).where(Member.name == member_name).options(selectinload(Member.tags))
        )
        t_res = await async_scoped_session.execute(select(Tag).where(Tag.name == tag_name))
        m, t = m_res.scalar_one_or_none(), t_res.scalar_one_or_none()

        if not m or not t: return "成员或标签不存在"
        if t in m.tags: return "已存在关联"

        m.tags.append(t)
        await async_scoped_session.commit()
        return "success"

    # --- 群组订阅相关 ---
    @staticmethod
    async def subscribe_group_tag(group_id: int, tag_name: str) -> str:
        # 1. 获取标签
        t_res = await async_scoped_session.execute(select(Tag).where(Tag.name == tag_name))
        tag = t_res.scalar_one_or_none()
        if not tag: return "标签不存在"

        # 2. 获取或创建群组 (使用 get 方法)
        group = await async_scoped_session.get(GrouP, group_id)
        if not group:
            group = GrouP(group_id=group_id, group_name="未知群聊", birthday_type="all")
            async_scoped_session.add(group)
            await async_scoped_session.flush()

        # 3. 关联订阅 (需要重新加载以获取 relationship)
        stmt = select(GrouP).where(GrouP.group_id == group_id).options(selectinload(GrouP.subscribed_tags))
        group_obj = (await async_scoped_session.execute(stmt)).scalar_one()

        if tag in group_obj.subscribed_tags: return "已经订阅过了"
        group_obj.subscribed_tags.append(tag)
        await async_scoped_session.commit()
        return "success"

    @staticmethod
    async def get_subscribed_groups_by_tags(tag_ids: List[int]) -> List[int]:
        stmt = select(GrouP.group_id).join(GroupSub).where(GroupSub.tag_id.in_(tag_ids)).distinct()
        res = await async_scoped_session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_tags() -> List[Tag]:
        stmt = select(Tag)
        res = await async_scoped_session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_members(month: Optional[str] = None) -> List[Member]:
        stmt = select(Member).options(selectinload(Member.tags))
        if month:
            # 筛选日期以 month- 开头的成员，例如 "10-"
            stmt = stmt.where(Member.date.like(f"{month}-%"))
        stmt = stmt.order_by(Member.date)
        res = await async_scoped_session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_subscribed_group_objects_by_tags(tag_ids: List[int]) -> List[GrouP]:
        """获取所有订阅了指定标签的群组完整对象"""
        async with async_scoped_session as session:
            from .models import GroupSub
            stmt = (
                select(GrouP)
                .join(GroupSub)
                .where(GroupSub.tag_id.in_(tag_ids))
                .distinct()
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())