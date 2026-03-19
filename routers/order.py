from fastapi import APIRouter, Depends, Request, Form
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import RedirectResponse

from repositories.database import get_db
from schemas.account import UserLogin
from schemas.order import Order, payWith
from services.order import add_order_for_user, pay_with_card_immediately
router = APIRouter()

@router.post("/create_order")
async def create_order(request: Request, order: Order = Form(), db: AsyncSession = Depends(get_db)):
    # Сохраняем заказ и получаем его из БД
    created_order = await add_order_for_user(request, order, db)

    # Проверяем оплату картой
    if order.payment_method == payWith.card_now:
        await pay_with_card_immediately()  # Тут в будущем можно будет передавать created_order.id
        # Можно даже сразу обновить статус:
        # created_order.is_paid = True
        # await db.commit()

    # Редиректим на страницу успешного заказа, используя реальный ID из базы!
    return RedirectResponse(url=f"/account", status_code=status.HTTP_302_FOUND)