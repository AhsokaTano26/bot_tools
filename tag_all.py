import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload

# 导入你的模型和配置
from standalone_init import Member, Tag, DB_URL


async def add_tag_to_all(target_tag_name: str):
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. 检查并获取目标标签
        res = await session.execute(select(Tag).where(Tag.name == target_tag_name))
        tag_obj = res.scalar_one_or_none()

        if not tag_obj:
            print(f"✨ 标签 [{target_tag_name}] 不存在，正在创建...")
            tag_obj = Tag(name=target_tag_name)
            session.add(tag_obj)
            await session.flush()
        else:
            print(f"📖 找到现有标签: [{target_tag_name}]")

        # 2. 获取所有成员，并预加载他们的标签关系
        print("🔍 正在检索全员数据...")
        stmt = select(Member).options(selectinload(Member.tags))
        all_members = (await session.execute(stmt)).scalars().all()

        # 3. 批量添加关联
        count = 0
        for m in all_members:
            if tag_obj not in m.tags:
                m.tags.append(tag_obj)
                count += 1

        await session.commit()
        print(f"✅ 处理完成！已为 {count} 位成员新增了 [{target_tag_name}] 标签。")
        print(f"📊 目前共有 {len(all_members)} 位成员拥有该标签。")


if __name__ == "__main__":
    # 你可以在这里修改你想要批量打的标签名
    TAG_NAME = "BanG_Dream!"

    asyncio.run(add_tag_to_all(TAG_NAME))