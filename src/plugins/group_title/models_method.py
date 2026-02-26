from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import get_session
from .models import Member, Tag, GrouP, MemberTag, GroupSub

class DBManager:
    # --- 成员相关 ---
    @staticmethod
    async def add_member(name: str, date: str, extra: str = "") -> bool:
        new_m = Member(name=name, date=date, extra=extra)
        # 调用 get_session() 获取当前实例
        get_session().add(new_m)
        await get_session().commit()
        return True

    @staticmethod
    async def get_members_by_date(date: str) -> List[Member]:
        stmt = select(Member).where(Member.date == date).options(selectinload(Member.tags))
        # 所有 execute 都要加 ()
        result = await get_session().execute(stmt)
        return list(result.scalars().all())

    # --- 标签相关 ---
    @staticmethod
    async def add_tag(name: str) -> bool:
        exists = await get_session().execute(select(Tag).where(Tag.name == name))
        if exists.scalar_one_or_none():
            return False
        get_session().add(Tag(name=name))
        await get_session().commit()
        return True

    @staticmethod
    async def bind_member_tag(member_name: str, tag_name: str) -> str:
        m_res = await get_session().execute(
            select(Member).where(Member.name == member_name).options(selectinload(Member.tags))
        )
        t_res = await get_session().execute(select(Tag).where(Tag.name == tag_name))
        m, t = m_res.scalar_one_or_none(), t_res.scalar_one_or_none()

        if not m or not t: return "成员或标签不存在"
        if t in m.tags: return "已存在关联"

        m.tags.append(t)
        await get_session().commit()
        return "success"

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
            # 如果群已存在，更新一下群名和类型（可选）
            group.group_name = group_name
            group.birthday_type = bir_type

        # 必须先 flush，确保数据库里有了这条记录，后续 join 查询才不会报 NoResultFound
        await session.flush()

        # 3. 关联订阅 (使用 selectinload 预加载关联表)
        stmt = (
            select(GrouP)
            .where(GrouP.group_id == group_id)
            .options(selectinload(GrouP.subscribed_tags))
        )
        result = await session.execute(stmt)
        group_obj = result.scalar_one()  # 此时一定能找到了

        if tag in group_obj.subscribed_tags:
            return "已经订阅过了"

        group_obj.subscribed_tags.append(tag)
        await session.commit()
        return "success"

    @staticmethod
    async def get_subscribed_groups_by_tags(tag_ids: List[int]) -> List[int]:
        stmt = select(GrouP.group_id).join(GroupSub).where(GroupSub.tag_id.in_(tag_ids)).distinct()
        res = await get_session().execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_tags() -> List[Tag]:
        stmt = select(Tag)
        res = await get_session().execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_members(month: Optional[str] = None) -> List[Member]:
        stmt = select(Member).options(selectinload(Member.tags))
        if month:
            stmt = stmt.where(Member.date.like(f"{month}-%"))
        stmt = stmt.order_by(Member.date)
        res = await get_session().execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_subscribed_group_objects_by_tags(tag_ids: List[int]) -> List[GrouP]:
        """获取所有订阅了指定标签的群组完整对象"""
        # 注意：nonebot-plugin-orm 的 scoped_session 不需要也不支持 async with 手动开启
        from .models import GroupSub
        stmt = (
            select(GrouP)
            .join(GroupSub)
            .where(GroupSub.tag_id.in_(tag_ids))
            .distinct()
        )
        res = await get_session().execute(stmt)
        return list(res.scalars().all())