import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 导入模型和配置
from standalone_init import Tag, DB_URL


async def add_tags_only_loop():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("🏷️  标签快速录入系统 (输入 'q' 退出)")
    print("-" * 30)

    async with async_session() as session:
        while True:
            tag_name = await asyncio.to_thread(input, "\n请输入要新建的标签名称: ")
            tag_name = tag_name.strip()

            if tag_name.lower() == 'q':
                break
            if not tag_name:
                continue

            # 1. 检查标签是否已存在
            stmt = select(Tag).where(Tag.name == tag_name)
            res = await session.execute(stmt)
            exists = res.scalar_one_or_none()

            if exists:
                print(f"📖 标签 [{tag_name}] 已经存在于数据库中，跳过。")
            else:
                # 2. 创建新标签
                new_tag = Tag(name=tag_name)
                session.add(new_tag)
                await session.commit()  # 立即提交
                print(f"✅ 成功创建新标签: [{tag_name}]")

    print("\n👋 标签录入结束。")


if __name__ == "__main__":
    try:
        asyncio.run(add_tags_only_loop())
    except KeyboardInterrupt:
        print("\n操作已强制中断")