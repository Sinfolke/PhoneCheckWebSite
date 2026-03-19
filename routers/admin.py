from fastapi import Form, Depends, HTTPException, APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from models.account import User
from models.order import OrderDB
from repositories.database import get_db
from utils import hashing

router = APIRouter()

@router.post("/admin/create-inspector")
async def create_inspector(
        name: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        user=Depends(hashing.user_by_jwt_token),
        db: AsyncSession = Depends(get_db)
):
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Проверяем, не занят ли email
    query = select(User).where(User.email == email)
    existing_user = (await db.execute(query)).scalar_one_or_none()

    if existing_user:
        # ВАРИАНТ Б: Просто обновляем роль существующего пользователя прямо тут
        if existing_user.role != "inspector":
            existing_user.role = "inspector"
            await db.commit()
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    # Создаем сразу инспектора
    new_inspector = User(
        email=email,
        name=name,
        hashed_password=hashing.hash_password(password),
        role="inspector"  # Задаем роль
    )
    db.add(new_inspector)
    await db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=302)

@router.post("/admin/change-role/{target_user_id}")
async def change_user_role(
        target_user_id: int,
        new_role: str = Form(...),
        user=Depends(hashing.user_by_jwt_token),
        db: AsyncSession = Depends(get_db)
):
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Защита: Админ не может случайно снять права сам с себя
    if target_user_id == user.id:
        return RedirectResponse(url="/admin/dashboard?error=cant_change_self", status_code=302)

    # Находим юзера и меняем роль
    query = select(User).where(User.id == target_user_id)
    target_user = (await db.execute(query)).scalar_one_or_none()

    if target_user and new_role in ["client", "inspector", "admin"]:
        target_user.role = new_role
        await db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=302)
@router.post("/admin/assign-inspector/{order_id}")
async def assign_inspector(
    order_id: int,
    inspector_id: int = Form(...), # Получаем ID выбранного инспектора из формы
    user = Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db)
):
    # Проверка на админа
    if not user or user.role != "admin":
        return RedirectResponse(url="/account", status_code=302)

    # Ищем заказ
    query = select(OrderDB).where(OrderDB.id == order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()

    if order:
        # Назначаем проверяющего
        order.inspector_id = inspector_id
        # Автоматически переводим заказ в статус "В работе"
        order.status = "assigned"
        await db.commit()

    # Возвращаем админа обратно на дашборд
    return RedirectResponse(url="/admin/dashboard", status_code=302)