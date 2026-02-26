import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from pathlib import Path

# 导入你的模型定义（确保路径正确，或使用之前脚本里的纯净版定义）
from standalone_init import Member, Tag, DB_URL, member_tag


async def interactive_tagging():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. 预加载所有标签到内存，方便快速查找
        res = await session.execute(select(Tag))
        tags_dict = {tag.name: tag for tag in res.scalars().all()}

        # 2. 获取所有成员及其现有标签
        stmt = select(Member).options(selectinload(Member.tags))
        members = (await session.execute(stmt)).scalars().all()

        print("🎸 BanG Dream 成员标签交互式编辑器")
        print("指令说明: ")
        print("  - 输入标签名（如 'MyGO'），多个用空格隔开（如 'MyGO 声优'）")
        print("  - 直接回车：跳过当前成员")
        print("  - 输入 'q'：保存并退出")
        print("-" * 40)

        for m in members:
            existing_tags = [t.name for t in m.tags]
            print(f"\n[当前成员]: {m.name} (生日: {m.date})")
            print(f"[已有标签]: {existing_tags if existing_tags else '无'}")

            # 阻塞式等待用户输入
            user_input = await asyncio.to_thread(input, "请输入要添加的标签 (q退出): ")

            if user_input.lower() == 'q':
                break
            if not user_input.strip():
                continue

            # 处理输入的标签
            input_tag_names = user_input.replace(',', ' ').split()

            for t_name in input_tag_names:
                # 如果标签库里没有这个标签，自动创建它
                if t_name not in tags_dict:
                    new_tag = Tag(name=t_name)
                    session.add(new_tag)
                    await session.flush()  # 拿到新标签的 ID
                    tags_dict[t_name] = new_tag
                    print(f"✨ 已创建新标签: {t_name}")

                target_tag = tags_dict[t_name]

                # 建立关联
                if target_tag not in m.tags:
                    m.tags.append(target_tag)
                    print(f"✅ 已关联 [{t_name}] 到 {m.name}")

            # 每改一个人就 flush 一次，防止意外崩溃导致白干
            await session.flush()

        await session.commit()
        print("\n💾 所有修改已保存至数据库。")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_tagging())
    except KeyboardInterrupt:
        print("\n强制退出，未提交的修改可能未保存。")