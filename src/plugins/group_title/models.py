from sqlalchemy import Column, String, Text, DateTime, INT, BOOLEAN
from typing import List
from sqlalchemy import ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from nonebot_plugin_orm import Model


# --- 中间关联表 1: 成员 <-> 标签 ---
class MemberTag(Model):
    __tablename__ = "member_tag"
    member_id: Mapped[int] = mapped_column(ForeignKey("member.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), primary_key=True)


# --- 中间关联表 2: 群组 <-> 订阅标签 ---
class GroupSub(Model):
    __tablename__ = "group_sub"
    group_id: Mapped[int] = mapped_column(ForeignKey("group.group_id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), primary_key=True)


# --- 标签主表 ---
class Tag(Model):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)  # 如 "Roselia", "MyGO"


# --- 成员表 (Member) ---
class Member(Model):
    __tablename__ = "member"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(64))
    extra: Mapped[str] = mapped_column(String(255), nullable=True)

    # 关系映射：通过中间表 MemberTag 关联到 Tag
    tags: Mapped[List["Tag"]] = relationship(
        secondary="member_tag",
        lazy="selectin"  # 自动预加载，方便异步环境直接访问 .tags
    )


# --- 群组配置表 (GrouP) ---
class GrouP(Model):
    __tablename__ = "group"
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(64))
    birthday_type: Mapped[int] = mapped_column(INT)

    # 关系映射：通过中间表 GroupSub 关联到 Tag
    subscribed_tags: Mapped[List["Tag"]] = relationship(
        secondary="group_sub",
        lazy="selectin"
    )