import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from pathlib import Path

# 导入模型和配置
from standalone_init import Member, Tag, DB_URL, TAG_MAPPING


async def add_member_loop():
    # 初始化数据库引擎
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("🆕 录入新成员系统 (输入 'q' 随时退出)")
    print("-" * 30)

    async with async_session() as session:
        # 先预加载所有标签，避免在循环里重复查询数据库
        res = await session.execute(select(Tag))
        all_tags = {t.name: t for t in res.scalars().all()}

        while True:
            print("\n--- 新成员录入 ---")
            name = await asyncio.to_thread(input, "请输入成员名字: ")
            if name.lower() == 'q':
                break

            date = await asyncio.to_thread(input, "请输入生日 (格式 MM-DD, 如 05-27): ")
            if date.lower() == 'q':
                break

            extra = await asyncio.to_thread(input, "请输入备注 (直接回车跳过): ")
            if extra.lower() == 'q':
                break

            if not name.strip() or not date.strip():
                print("❌ 名字和生日不能为空，请重新输入！")
                continue

            # 1. 检查是否已存在
            exists = (await session.execute(
                select(Member).where(Member.name == name, Member.date == date)
            )).scalar_one_or_none()

            if exists:
                print(f"⚠️ 成员 {name} ({date}) 已存在，跳过。")
                continue

            new_member = Member(name=name, date=date, extra=extra)

            # 2. 自动匹配标签
            found_tags = []
            for t_name, keywords in TAG_MAPPING.items():
                if any(kw in name for kw in keywords):
                    if t_name in all_tags:
                        new_member.tags.append(all_tags[t_name])
                        found_tags.append(t_name)

            session.add(new_member)
            # 每一位成员录入后即刻提交，防止崩溃导致数据丢失
            await session.commit()

            print(f"✅ 录入成功: {name} [{date}]")
            if found_tags:
                print(f"🔗 自动关联标签: {', '.join(found_tags)}")
            else:
                print("ℹ️ 未匹配到预设标签")

    print("\n👋 录入工作已结束，数据库已保存。")


if __name__ == "__main__":
    try:
        asyncio.run(add_member_loop())
    except KeyboardInterrupt:
        print("\n操作被用户强制中断")