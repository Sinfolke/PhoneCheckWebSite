from sqlalchemy import Column, Integer, String, Table
from sqlalchemy.orm import relationship

from repositories.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

    role = Column(String, default="client")  # Может быть "client", "inspector", "admin"
    # Правильная связь: один пользователь -> много заказов
    # ИСПРАВЛЕННАЯ СТРОКА: Указываем foreign_keys строкой
    orders = relationship(
        "OrderDB",
        foreign_keys="[OrderDB.user_id]",
        back_populates="owner",
        cascade="all, delete-orphan"
    )