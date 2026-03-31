from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship

from repositories.database import Base

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship


class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    # 1. Связь с Клиентом (Владельцем)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship(
        "User",
        foreign_keys="[OrderDB.user_id]",  # ИСПРАВЛЕННАЯ СТРОКА
        back_populates="orders"
    )

    # 2. Связь с Инспектором
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    inspector = relationship(
        "User",
        foreign_keys="[OrderDB.inspector_id]"  # ИСПРАВЛЕННАЯ СТРОКА
    )

    client_name = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    device_model = Column(String, nullable=False)
    ad_link = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    meeting_time = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)

    status = Column(String, default="pending")
    is_paid = Column(Boolean, default=False)

    imei = Column(String, nullable=False)
    serial = Column(String, nullable=False)