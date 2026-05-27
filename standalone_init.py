import asyncio
from sqlalchemy import Column, String, Integer, ForeignKey, BigInteger, Table, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Mapped, mapped_column
from typing import List
from pathlib import Path

# --- 1. 纯净模型定义 (不依赖 nonebot) ---
Base = declarative_base()

# 中间表 1: 成员 <-> 标签
member_tag = Table(
    "member_tag",
    Base.metadata,
    Column("member_id", ForeignKey("member.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)

# 中间表 2: 群组 <-> 标签
group_sub = Table(
    "group_sub",
    Base.metadata,
    Column("group_id", ForeignKey("group.group_id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tag"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True)


class Member(Base):
    __tablename__ = "member"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10))
    name = Column(String(64))
    extra = Column(String(255))
    tags = relationship("Tag", secondary=member_tag, lazy="selectin")


class GrouP(Base):
    __tablename__ = "group"
    group_id = Column(BigInteger, primary_key=True)
    group_name = Column(String(64))
    birthday_type = Column(Integer)
    subscribed_tags = relationship("Tag", secondary=group_sub, lazy="selectin")


# --- 2. 数据库配置 ---
# 自动定位你的数据库文件路径
BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "data" / "db.sqlite3"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# --- 3. 数据与匹配逻辑 ---
TAG_MAPPING = {
    "BanG_Dream!": ["高松灯", "千早爱音", "要乐奈", "长崎爽世", "椎名立希", "羊宫妃那", "立石凛", "青木阳菜", "小日向美香",
             "林鼓子","凑友希那", "冰川纱夜", "今井莉莎", "宇田川亚子", "白金磷子", "相羽爱奈", "工藤晴香", "中岛由贵","樱川惠", "志崎烨音", "明坂聪美", "远藤祐里香",
                   "丰川祥子", "若叶睦", "八幡海铃", "三角初华", "祐天寺若麦", "佐佐木李子", "渡濑结月", "小日向美香","冈田梦以", "米泽茜",
                   "高松灯", "丰川祥子", "若叶睦", "长崎爽世", "椎名立希",
                   "丸山彩", "冰川日菜", "白鹭千圣", "大和麻弥", "若宫伊芙", "前岛亜美", "小泽亚李", "上坂堇","中上育实", "秦佐和子",
                   "美竹兰", "青叶摩卡", "上原绯玛丽", "宇田川巴", "羽泽鸫", "佐仓绫音", "三泽纱千香", "加藤英美里","日笠阳子", "金元寿子",
                   "户山香澄", "花园多惠", "牛込里美", "山吹沙绫", "市谷有咲", "爱美", "大塚纱英", "西本里美","大桥彩香", "伊藤彩沙",
                   "弦卷心", "濑田薰", "北泽育美", "松原花音", "奥泽美咲", "伊藤美来", "田所梓", "吉田有里","丰田萌绘", "黑泽朋世",
                   "和奏瑞依", "朝日六花", "佐藤益木", "鳰原令王那", "珠手知由", "Raychell", "小原莉子", "夏芽","仓知玲凤", "纺木吏佐"],
}

RAW_BIRTHDAY_DATA = [
    ('01-02', '明坂聪美', ''), ('01-05', '青木阳菜', ''), ('01-07', '羽泽鸫', ''),
    ('01-13', '和奏瑞依&Raychell&三泽纱千香', ''), ('01-14', '若叶睦', ''), ('01-29', '佐仓绫音', ''),
    ('02-03', '小原莉子', ''), ('02-07', '峰月律', ''), ('02-08', '志崎烨音', ''),
    ('02-14', '丰川祥子', ''), ('02-18', '渡濑结月', ''), ('02-19', '仓田真白', ''),
    ('02-22', '要乐奈', ''), ('02-28', '濑田薰', ''), ('03-14', '小日向美香', ''),
    ('03-15', '丰田萌绘', ''), ('03-16', '工藤晴香', ''), ('03-20', '冰川纱夜&冰川日菜', ''),
    ('03-23', '牛込里美', ''), ('03-25', '鳰原令王那', ''), ('03-26', '羊宫妃那', ''),
    ('03-31', '西尾夕香', ''), ('04-06', '白鹭千圣', ''), ('04-07', '八幡海铃', ''),
    ('04-10', '美竹兰&黑泽朋世', ''), ('04-15', '宇田川巴', ''), ('04-17', '宫永野乃花&直田姬奈', ''),
    ('04-20', '进藤天音', ''), ('05-11', '松原花音', ''), ('05-12', '佐藤益木', ''),
    ('05-15', '林鼓子', ''), ('05-19', '山吹沙绫&冈田梦以', ''), ('05-22', '仓知玲凤', ''),
    ('05-27', '长崎爽世', ''), ('06-01', '祐天寺若麦', ''), ('06-16', '广町七深', ''),
    ('06-18', '中上育实', ''), ('06-24', 'mika@远藤祐里香', ''), ('06-26', '三角初华', ''),
    ('06-27', '若宫伊芙', ''), ('07-03', '宇田川亚子', ''), ('07-05', '纺木吏佐', ''),
    ('07-10', '立石凛', ''), ('07-14', '户山香澄', ''), ('07-16', '日笠阳子', ''),
    ('07-17', '朝日六花', ''), ('07-20', '夏芽', ''), ('07-30', '北泽育美', ''),
    ('08-08', '弦卷心', ''), ('08-09', '椎名立希', ''), ('08-10', '小泽亚李', ''),
    ('08-16', '仲町阿拉蕾', ''), ('08-17', '伊藤彩沙', ''), ('08-18', '吉田有里', ''),
    ('08-25', '今井莉莎', ''), ('09-03', '青叶摩卡', ''), ('09-08', '千早爱音', ''),
    ('09-10', '高尾奏音', ''), ('09-12', '中岛由贵', ''), ('09-13', '大桥彩香', ''),
    ('09-14', '秦佐和子', ''), ('09-15', '二叶筑紫', ''), ('09-19', '藤都子', ''),
    ('10-01', '奥泽美咲/米歇尔', ''), ('10-10', '大塚纱英', ''), ('10-12', '伊藤美来', ''),
    ('10-17', '白金磷子&相羽爱奈', ''), ('10-19', 'Ayasa', ''), ('10-23', '上原绯玛丽', ''),
    ('10-24', '樱川惠', ''), ('10-25', '西本里美', ''), ('10-26', '凑友希那', ''),
    ('10-27', '市谷有咲', ''), ('11-03', '大和麻弥', ''), ('11-04', '千石由乃', ''),
    ('11-10', '田所梓&佐佐木李子', ''), ('11-19', '八潮瑠唯', ''), ('11-22', '高松灯&前岛亜美', ''),
    ('11-26', '加藤英美里', ''), ('12-04', '花园多惠', ''), ('12-07', '珠手知由', ''),
    ('12-16', '金元寿子&桐谷透子', ''), ('12-19', '上坂堇', ''), ('12-25', '爱美', ''),
    ('12-27', '丸山彩', ''), ('12-31', '米泽茜', '')
]


async def init_task():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # 清理旧数据
        from sqlalchemy import delete
        await session.execute(delete(member_tag))
        await session.execute(delete(Member))
        await session.execute(delete(Tag))
        print("🧹 已清空旧数据，开始按独立成员拆分写入...")

        # 1. 获取/创建标签对象
        tag_objs = {}
        for t_name in TAG_MAPPING.keys():
            tag = (await session.execute(select(Tag).where(Tag.name == t_name))).scalar_one_or_none()
            if not tag:
                tag = Tag(name=t_name)
                session.add(tag)
            tag_objs[t_name] = tag
        await session.flush()

        # 2. 遍历原始数据并拆分
        added_count = 0
        for date, full_name, extra in RAW_BIRTHDAY_DATA:
            # 处理分隔符，统一按 & 拆分
            names_to_process = full_name.replace('/', '&').split('&')

            for individual_name in names_to_process:
                individual_name = individual_name.strip()
                if not individual_name:
                    continue

                # 检查这个独立名字是否已存在（防止数据中有重复）
                exists = (await session.execute(
                    select(Member).where(Member.name == individual_name, Member.date == date)
                )).scalar_one_or_none()
                if exists: continue

                # 创建独立成员记录
                new_member = Member(date=date, name=individual_name, extra=extra)

                # 为该成员匹配标签
                for t_name, keywords in TAG_MAPPING.items():
                    if any(kw in individual_name for kw in keywords):
                        new_member.tags.append(tag_objs[t_name])

                session.add(new_member)
                added_count += 1

        await session.commit()
        print(f"🚀 初始化成功！共存入 {added_count} 名独立成员。")


if __name__ == "__main__":
    asyncio.run(init_task())