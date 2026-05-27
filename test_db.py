import asyncio
from sqlalchemy import select, BigInteger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from pathlib import Path

# --- 导入或重新定义模型（为了脱离 NoneBot，我们直接用简版定义） ---
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Integer, ForeignKey, Table

Base = declarative_base()

# 定义与初始化脚本一致的表结构
member_tag = Table(
    "member_tag", Base.metadata,
    Column("member_id", ForeignKey("member.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)

group_sub = Table(
    "group_sub", Base.metadata,
    Column("group_id", ForeignKey("group.group_id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tag"
    id = Column(Integer, primary_key=True)
    name = Column(String(32))


class Member(Base):
    __tablename__ = "member"
    id = Column(Integer, primary_key=True)
    date = Column(String(10))
    name = Column(String(64))
    extra = Column(String(255), nullable=True)
    tags = relationship("Tag", secondary=member_tag, lazy="selectin")


class GrouP(Base):
    __tablename__ = "group"
    group_id = Column(BigInteger, primary_key=True)
    group_name = Column(String(64))
    birthday_type = Column(Integer)


# --- 配置 ---
DB_PATH = Path(__file__).parent / "data" / "db.sqlite3"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# --- 测试数据设定 ---
TEST_DATE = "01-13"  # 模拟凑友希那的生日
TEST_GROUP_ID = 123456789


async def run_test():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print(f"🔍 正在测试日期: {TEST_DATE}\n" + "=" * 30)

        # 1. 模拟：手动给一个测试群组订阅 "Roselia" 标签
        # 先确保标签存在
        res = await session.execute(select(Tag).where(Tag.name == "Roselia"))
        roselia_tag = res.scalar_one_or_none()


        # 2. 核心逻辑测试：查找今日生日成员
        stmt = select(Member).where(Member.date == TEST_DATE)
        result = await session.execute(stmt)
        birthday_members = result.scalars().all()

        if not birthday_members:
            print("❌ 该日期没有人过生日。")
            return

        for member in birthday_members:
            print(f"🎂 发现生日成员: {member.name}")
            member_tags = [t.name for t in member.tags]
            print(f"🏷️  该成员标签: {member_tags}")

            # 3. 查找订阅了这些标签的群组
            tag_ids = [t.id for t in member.tags]
            group_stmt = (
                select(GrouP)
                .join(group_sub)
                .where(group_sub.c.tag_id.in_(tag_ids))
                .distinct()
            )
            groups_to_notify = (await session.execute(group_stmt)).scalars().all()

            if groups_to_notify:
                for g in groups_to_notify:
                    print(f"📢 准备推送至群: {g.group_name} ({g.group_id})")
            else:
                print("📭 没有群组订阅相关标签，不推送。")


if __name__ == "__main__":
    asyncio.run(run_test())