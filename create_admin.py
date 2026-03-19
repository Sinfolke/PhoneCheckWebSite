import asyncio
import getpass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Твои импорты. Возможно, тебе придется немного поправить названия,
# если они у тебя называются иначе.
from repositories.database import AsyncSessionLocal
from models.order import OrderDB
from models.account import User
from utils.hashing import hash_password  # Твоя функция хэширования пароля


async def create_superuser():
    print("\n=== Создание Суперпользователя (Админа) ===")

    # 1. Запрашиваем данные у пользователя в терминале
    email = input("Введите email: ").strip()
    name = input("Введите имя: ").strip()

    # getpass скрывает вводимые символы (как при вводе пароля в Ubuntu)
    password = getpass.getpass("Введите пароль: ")
    password_confirm = getpass.getpass("Повторите пароль: ")

    # 2. Базовые проверки
    if not email or not name or not password:
        print("❌ Ошибка: Все поля обязательны для заполнения!")
        return

    if password != password_confirm:
        print("❌ Ошибка: Пароли не совпадают!")
        return

    # 3. Работа с базой данных
    print("\nПодключение к базе данных...")

    # Создаем контекст сессии (подставь свой объект создания сессии)
    async with AsyncSessionLocal() as session:
        # Проверяем, свободен ли email
        query = select(User).where(User.email == email)
        result = await session.execute(query)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"❌ Ошибка: Пользователь с email '{email}' уже существует.")

            # Если юзер есть, можем предложить обновить ему роль до админа
            upgrade = input("Хотите выдать ему права администратора? (y/n): ")
            if upgrade.lower() == 'y':
                existing_user.role = "admin"
                await session.commit()
                print("✅ Права администратора успешно выданы!")
            return

        # 4. Создаем нового админа
        hashed_pw = hash_password(password)
        new_admin = User(
            email=email,
            name=name,
            hashed_password=hashed_pw,
            role="admin"  # Жестко задаем роль админа
        )

        session.add(new_admin)
        await session.commit()
        print(f"✅ Суперпользователь '{name}' ({email}) успешно создан!")


if __name__ == "__main__":
    # Запускаем асинхронную функцию в синхронном блоке if __name__ == "__main__"
    asyncio.run(create_superuser())