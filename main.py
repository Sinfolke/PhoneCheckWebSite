from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

import utils.config as config_md
import utils.hashing as hashing
import routers.account
from repositories.database import engine, Base  # Импортируй свои engine и Base
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
    # 2. Указываем FastAPI, что нужно получить пользователя через зависимость
    user = Depends(hashing.user_by_jwt_token)
):
    # 3. Если токена нет или он неверный, перекидываем на логин
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # 4. Если всё ок, рендерим шаблон
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user
    })
@app.get("/order/full-check")
async def full_check_page(request: Request, user = Depends(hashing.user_by_jwt_token)):
    return templates.TemplateResponse("full_check.html", {
        "request": request,
        "user": user
    })
app.include_router(routers.account.router)