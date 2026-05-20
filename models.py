from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    is_admin = Column(Integer, default=0)
    is_banned = Column(Integer, default=0)


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=False)

    level_id = Column(Integer, default=1)

    clear_time = Column(DECIMAL(10, 2), default=0)
    sanity_left = Column(Integer, default=100)
    pulses_used = Column(Integer, default=0)

    final_score = Column(Integer, default=0)

    date_earned = Column(TIMESTAMP, server_default=func.now())

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(255), nullable=False)
    username = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())