from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

import utils.config as config_md
import utils.hashing as hashing
import routers.account
import routers.order
import routers.admin
import routers.inspector
import routers.OCR
from models.order import OrderDB
from repositories.database import engine, Base, get_db  # Импортируй свои engine и Base
from models.account import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, который выполняется ДО старта сервера
    async with engine.begin() as conn:
        # run_sync нужен, потому что create_all это синхронная функция,
        # а драйвер asyncpg - асинхронный
        await conn.run_sync(Base.metadata.create_all)

    yield  # Сервер работает

    # Код, который выполняется ПОСЛЕ остановки сервера (пока оставим пустым)
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
config = config_md.readYaml("config.yaml")
# 1. ЗАГРУЖАЕМ НЕЙРОСЕТЬ ОДИН РАЗ ПРИ СТАРТЕ СЕРВЕРА
# gpu=False (если на сервере нет видеокарты NVIDIA). Если есть - ставь True, будет летать!
@app.get("/")
def root(request: Request, lang: str = "ua"):
    return templates.TemplateResponse("main.html", {
        "request": request,
        "t": config_md.getLanguageMetadata(lang),
        "price": config.get("check_price", 0),
        "on_site_visit": config.get("on_site_visit", {}),
        "check_list": config.get("check_list", []),
        "languages": config.get("languages", {}),
    })
@app.get("/login")
def login(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
    })
@app.get("/register")
def register(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request
    })

@app.get("/account")
async def account_page(
    request: Request,
    user = Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db) # Добавляем сессию БД
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # 1. Безопасно достаем все заказы пользователя, сортируя от новых к старым (desc)
    query = select(OrderDB).where(OrderDB.user_id == user.id).order_by(OrderDB.id.desc())
    result = await db.execute(query)
    orders = result.scalars().all() # Получаем список объектов OrderDB

    # 2. Инициализируем пустые списки (синтаксис Python)
    pending_checks = []
    recent_checks = []
    last_check = None

    # 3. Распределяем заказы по спискам
    for order in orders:
        if order.status != "completed":
            pending_checks.append(order) # В Питоне используем append вместо push
        else:
            recent_checks.append(order)
            # Так как мы отсортировали запросом новые заказы первыми,
            # первая встретившаяся завершенная проверка и будет "последней"
            if last_check is None:
                last_check = order

    # 4. Рендерим шаблон
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "pending_checks": pending_checks,
        "last_check": last_check,
        "recent_checks": recent_checks, # В историю передаем только завершенные
    })
@app.get("/order/full-check")
async def full_check_page(request: Request, user = Depends(hashing.user_by_jwt_token)):
    return templates.TemplateResponse("full_check.html", {
        "request": request,
        "user": user
    })
@app.get("/orders/{order_id}")
async def order_details_page(
    order_id: int,
    request: Request,
    user = Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Достаем заказ из базы
    query = select(OrderDB).where(OrderDB.id == order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()

    # Если заказ не найден или он чужой — отдаем ошибку 404
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Рендерим шаблон
    return templates.TemplateResponse("order_details.html", {
        "request": request,
        "user": user,
        "order": order
    })


@app.get("/inspector/dashboard")
async def inspector_dashboard(
        request: Request,
        user=Depends(hashing.user_by_jwt_token),
        db: AsyncSession = Depends(get_db)
):
    # 1. Проверяем авторизацию
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # 2. ПРОВЕРКА ПРАВ: Пускаем только инспекторов (и админов, если нужно)
    if user.role not in ["inspector", "admin"]:
        # Если обычный клиент попытается зайти по этой ссылке - кидаем его в его обычный кабинет
        return RedirectResponse(url="/account", status_code=302)

        # 3. Достаем заказы, которые назначены ИМЕННО ЭТОМУ проверяющему
    query = select(OrderDB).where(OrderDB.inspector_id == user.id).order_by(OrderDB.meeting_time.asc())
    result = await db.execute(query)
    assigned_orders = result.scalars().all()

    # Разделяем на активные и завершенные для удобства
    active_tasks = [o for o in assigned_orders if o.status != "completed"]
    completed_tasks = [o for o in assigned_orders if o.status == "completed"]

    return templates.TemplateResponse("inspector_dashboard.html", {
        "request": request,
        "user": user,
        "active_tasks": active_tasks,
        "completed_tasks": completed_tasks
    })
@app.get("/admin/dashboard")
async def admin_dashboard(request: Request, user=Depends(hashing.user_by_jwt_token), db: AsyncSession = Depends(get_db)):
    if not user or user.role != "admin":
        return RedirectResponse(url="/account", status_code=302)

    # Достаем заказы
    orders_query = select(OrderDB).order_by(OrderDB.id.desc())
    orders = (await db.execute(orders_query)).scalars().all()

    # Достаем инспекторов (для выпадающего списка в заказах)
    inspectors_query = select(User).where(User.role != "inspector" or User.role == "admin")
    inspectors = (await db.execute(inspectors_query)).scalars().all()

    # НОВОЕ: Достаем ВСЕХ пользователей, чтобы управлять их ролями
    users_query = select(User).order_by(User.id.desc())
    all_users = (await db.execute(users_query)).scalars().all()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "user": user,
        "orders": orders,
        "inspectors": inspectors,
        "all_users": all_users  # Передаем в шаблон
    })
@app.get("/inspector/report/{order_id}")
async def inspector_report_page(
    order_id: int,
    request: Request,
    user=Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db)
):
    if not user or user.role != "inspector" and user.role != "admin":
        return RedirectResponse(url="/login", status_code=302)

    query = select(OrderDB).where(OrderDB.id == order_id, OrderDB.inspector_id == user.id)
    order = (await db.execute(query)).scalar_one_or_none()

    if not order or order.status != "in_progress":
        return RedirectResponse(url="/inspector/dashboard", status_code=302)

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": user,
        "order": order
    })
app.include_router(routers.account.router)
app.include_router(routers.order.router)
app.include_router(routers.admin.router)
app.include_router(routers.inspector.router)
app.include_router(routers.OCR.router)