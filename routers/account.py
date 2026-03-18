from fastapi import APIRouter, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from repositories.database import get_db
from schemas.account import UserCreate, UserResponse, UserLogin
import services.account as Service
router = APIRouter()


@router.post("/register")
async def register_router(name: str = Form(), email: str = Form(), password: str = Form(), db: AsyncSession = Depends(get_db)):
    await Service.register(UserCreate(email=email, name=name, password=password), db)
    response = RedirectResponse(url="/login", status_code=302)
    return response

@router.post("/login")
async def login_router(email: str = Form(), password: str = Form(), db: AsyncSession = Depends(get_db)):
    result = await Service.login(UserLogin(email=email, password=password), db)
    # 3. Делаем редирект в личный кабинет
    # status_code=302 говорит браузеру: "Успешно, перейди на эту страницу"
    response = RedirectResponse(url="/account", status_code=302)

    # 4. Высчитываем время жизни куки (если нажал "Запомнить меня" — 30 дней, иначе 1 час)
    cookie_max_age = 30 * 24 * 60 * 60

    # 5. СОХРАНЯЕМ ТОКЕН (браузер получит эту команду и сохранит куку)
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,  # Важно! Защищает от кражи токена хакерами через JavaScript
        max_age=cookie_max_age,
        samesite="lax",
        secure=False  # На продакшене (с HTTPS) обязательно поменяй на True
    )

    return response
