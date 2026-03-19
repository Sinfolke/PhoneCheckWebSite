from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from models.order import OrderDB
from repositories.database import get_db
from utils import hashing

router = APIRouter()

@router.post("/inspector/accept/{order_id}")
async def accept_order(
    order_id: int,
    user=Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db)
):
    # Пускаем только инспекторов
    if not user or user.role != "inspector" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Ищем заказ, который назначен именно на этого инспектора
    query = select(OrderDB).where(OrderDB.id == order_id, OrderDB.inspector_id == user.id)
    order = (await db.execute(query)).scalar_one_or_none()

    if order and order.status == "assigned":
        order.status = "accepted"
        await db.commit()

    return RedirectResponse(url="/inspector/dashboard", status_code=302)

@router.post("/inspector/confirm/{order_id}")
async def confirm_order(order_id: int, user=Depends(hashing.user_by_jwt_token), db: AsyncSession = Depends(get_db)):
    if not user or user.role != "inspector" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    query = select(OrderDB).where(OrderDB.id == order_id, OrderDB.inspector_id == user.id)
    order = (await db.execute(query)).scalar_one_or_none()

    # Если мы договорились с клиентом, переводим в работу
    if order and order.status == "accepted":
        order.status = "in_progress"
        await db.commit()

    return RedirectResponse(url="/inspector/dashboard", status_code=302)

@router.post("/inspector/cancel/{order_id}")
async def cancel_order(
        order_id: int,
        cancel_reason: str = Form(...),
        cancel_comment: str | None = Form(None),  # Комментарий необязателен
        user=Depends(hashing.user_by_jwt_token),
        db: AsyncSession = Depends(get_db)
):
    # Пускаем только инспекторов
    if not user or user.role != "inspector" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Ищем заказ (проверяем, что он висит именно на этом инспекторе)
    query = select(OrderDB).where(OrderDB.id == order_id, OrderDB.inspector_id == user.id)
    order = (await db.execute(query)).scalar_one_or_none()

    # Отменить можно только если статус не in_progress и не completed
    if order and order.status not in ["in_progress", "completed"]:
        # Сбрасываем инспектора и возвращаем заказ в общий пул новых заявок
        order.inspector_id = None
        order.status = "pending"

        await db.commit()

    return RedirectResponse(url="/inspector/dashboard", status_code=302)