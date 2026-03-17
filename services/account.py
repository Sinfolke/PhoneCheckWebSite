from repositories.database import get_db
from schemas.account import UserResponse, UserCreate, UserLogin
from models.account import User
from http.client import HTTPException
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import utils.hashing as hashing


async def register(us: UserCreate, db: AsyncSession):
    query = select(User).where(User.email == us.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email has already been registered",
        )

    # 2. Хешируем пароль
    hashed_pwd = hashing.hash_password(us.password)

    # 3. Создаем объект пользователя (пароль в чистом виде забываем!)
    new_user = User(email=us.email, hashed_password=hashed_pwd)

    # 4. Сохраняем в базу данных
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)  # Получаем ID, который сгенерировала БД

    # Возвращаем пользователя (Pydantic сам отфильтрует данные по схеме UserResponse)
    return new_user

async def login(user_credentials: UserLogin, db: AsyncSession):
    query = select(User).where(User.email == user_credentials.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not hashing.verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = hashing.create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}