import jwt
import os
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.account import User
from sqlalchemy import select

from repositories.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def user_by_jwt_token(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")

    print(f"1. Токен из куки: {token}")  # Смотрим, пришел ли токен вообще

    if not token:
        print("-> Токена нет, возвращаем None")
        return None

    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        # Проверь, совпадает ли SECRET_KEY здесь с тем, которым ты создавал токен!
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        print(f"2. Успешно расшифровали, email: {email}")

        if email is None:
            return None

    except jwt.ExpiredSignatureError:
        print("-> Ошибка: Токен просрочен!")
        return None
    except jwt.PyJWTError as e:
        print(f"-> Ошибка расшифровки JWT: {e}")
        return None

    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    print(f"3. Нашли пользователя в БД: {user}")
    return user