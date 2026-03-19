from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.account import User
from models.order import OrderDB
from repositories.database import get_db
from schemas.account import UserLogin
from schemas.order import Order

from utils.hashing import user_by_jwt_token

async def add_order_for_user(request: Request, order_data: Order, db: AsyncSession = Depends(get_db)):
    # 1. Получаем пользователя
    user = await user_by_jwt_token(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не авторизован"
        )

    # 2. Создаем запись в базе данных
    new_order = OrderDB(
        user_id=user.id,
        client_name=order_data.name,
        contact=order_data.contact,
        device_model=order_data.model,
        ad_link=order_data.ad_link,
        latitude=order_data.latitude,
        longitude=order_data.longitude,
        meeting_time=order_data.meeting_time,
        payment_method=order_data.payment_method.value, # .value вытащит строку из Enum (cash/card-now)
        status="pending", # Статус по умолчанию при создании
        is_paid=False     # Изначально не оплачено
    )

    # 3. Сохраняем в БД
    db.add(new_order)
    await db.commit()          # Фиксируем изменения
    await db.refresh(new_order) # Обновляем объект, чтобы получить его сгенерированный ID

    # Возвращаем созданный заказ в роутер
    return new_order
async def pay_with_card_immediately():
    return