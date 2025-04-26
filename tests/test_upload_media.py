from sqlalchemy import select

import pytest
from main.models import User, Media
from .factories import UserFactory


@pytest.mark.asyncio
async def test_upload_file(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Создаём тестовый файл
    file_path = "tests/test_image.jpeg"
    with open(file_path, "rb") as file:
        files = {"file": (file_path, file, "image/jpeg")}

        # Отправляем запрос с файлом
        response = await async_client.post(
            "/api/medias",
            headers={"api-key": user._raw_api_key},
            files=files,  # Передаём файл через параметр files
        )

    assert response.status_code == 200

    # Проверяем, что файл сохранен в базе данных
    media = (await db_session.execute(select(Media))).scalars().first()
    assert media is not None


@pytest.mark.asyncio
async def test_upload_file_without_file(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Отправляем запрос без файла
    response = await async_client.post("/api/medias", headers={"api-key": user._raw_api_key})

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)

    # Проверяем, что ошибка связана с отсутствием файла
    assert any(item["loc"] == ["body", "file"] for item in data["detail"])


@pytest.mark.asyncio
async def test_upload_file_not_allowed(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Создаём тестовый файл, который не является картинкой
    file_path = "tests/test_txt_file.txt"
    with open(file_path, "rb") as file:
        files = {"file": (file_path, file, "image/jpeg")}

        # Отправляем запрос с файлом
        response = await async_client.post(
            "/api/medias",
            headers={"api-key": user._raw_api_key},
            files=files,  # Передаём файл через параметр files
        )

    assert response.status_code == 400
    data = response.json()
    assert data["result"] == "false"
    assert data["error_type"] == "FileError"
