from os import getenv
from dotenv import load_dotenv
import pytest
import pytest_asyncio
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from main.app import app
from main.models import Base
from pytest_factoryboy import register
from .factories import UserFactory, TweetFactory
from httpx import AsyncClient, ASGITransport
from main.database.db_init import get_db
import sys

sys.path.insert(0, ".")

# Конфигурация тестовой БД
load_dotenv()

DB_USER = getenv(
    "DB_USER",
)

DB_PASSWORD = getenv(
    "DB_PASSWORD",
)

TEST_SQLALCHEMY_DATABASE_URI = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@postgres-test:5432/test_db"
)

test_engine = create_async_engine(TEST_SQLALCHEMY_DATABASE_URI)
TestAsyncSessionLocal = sessionmaker(
    test_engine, expire_on_commit=False, class_=AsyncSession
)

# Регистрация фабрик
register(UserFactory)
register(TweetFactory)


# Фикстура для управления тестовой БД (создание и удаление таблиц)
@pytest_asyncio.fixture(scope="function", autouse=True)
async def manage_test_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Создаем таблицы перед тестом
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # Удаляем таблицы после теста


# Фикстура для тестовой сессии
@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# Фикстура для тестового клиента
@pytest_asyncio.fixture
async def async_client(db_session):
    # Переопределяем зависимость get_db
    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Удаляем переопределение после завершения тестов
    app.dependency_overrides = {}


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# Фикстура для создания тестового файла
@pytest.fixture
def test_file():
    file_path = "tests/test_image.jpeg"
    return file_path
