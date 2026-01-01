from typing import Optional
from sqlalchemy import text
from nonebot_plugin_orm import async_scoped_session
from sqlalchemy import select
from .models import BanG , GrouP


class BanGManger:
    @classmethod
    async def get_all_student_id(cls, session: async_scoped_session) -> set:
        """获取数据库中所有 student_id"""
        result = await session.execute(select(BanG.date))
        return {row[0] for row in result}

    @classmethod
    async def get_Sign_by_student_id(cls, session: async_scoped_session, student_id: int) -> Optional[BanG]:
        """根据 student_id 获取单个信息"""
        return await session.get(BanG, student_id)

    @staticmethod
    async def is_database_empty(db_session):
        # 查询数据库，判断是否有数据
        result = await db_session.execute(text("SELECT 1 FROM BanG LIMIT 1"))
        return not result.fetchone()

    @classmethod
    async def create_signmsg(cls, session: async_scoped_session, **kwargs) -> BanG:
        """创建新的数据"""
        new_signmsg = BanG(**kwargs)
        session.add(new_signmsg)
        await session.commit()
        return new_signmsg


class GrouPManger:
    @classmethod
    async def get_all_student_id(cls, session: async_scoped_session) -> set:
        """获取数据库中所有 student_id"""
        result = await session.execute(select(GrouP.group_id))
        return {row[0] for row in result}

    @classmethod
    async def get_Sign_by_student_id(cls, session: async_scoped_session, student_id: int) -> Optional[GrouP]:
        """根据 student_id 获取单个信息"""
        return await session.get(GrouP, student_id)

    @staticmethod
    async def is_database_empty(db_session):
        # 查询数据库，判断是否有数据
        result = await db_session.execute(text("SELECT 1 FROM GrouP LIMIT 1"))
        return not result.fetchone()

    @classmethod
    async def create_signmsg(cls, session: async_scoped_session, **kwargs) -> GrouP:
        """创建新的数据"""
        new_signmsg = GrouP(**kwargs)
        session.add(new_signmsg)
        await session.commit()
        return new_signmsg

    @classmethod
    async def delete_id(cls, session: async_scoped_session, id: str) -> bool:
        """删除数据"""
        lanmsg = await cls.get_Sign_by_student_id(session, id)
        if lanmsg:
            await session.delete(lanmsg)
            await session.commit()
            return True
        return False