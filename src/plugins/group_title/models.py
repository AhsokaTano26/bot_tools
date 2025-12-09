from nonebot_plugin_orm import Model
from sqlalchemy import Column, String, Text, DateTime, INT, BOOLEAN


class BanG(Model):
    __tablename__ = "BanG"
    date = Column(String(255), primary_key=True, nullable=True)
    name = Column(String(255), nullable=True)
    extra = Column(String(255), nullable=True)

class GrouP(Model):
    __tablename__ = "Group"
    group_id = Column(INT, primary_key=True, nullable=True)
    group_name = Column(String(255), nullable=True)
    birthday_name = Column(String(255), nullable=True)