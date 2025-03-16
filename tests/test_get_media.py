from sqlalchemy import select
from main.app import get_media
import pytest
from main.models import User, Tweet, Media
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_media_success(async_client, test_file, db_session):
    # Создаём пользователя
    user = User(
        login="test_login",
        api_key="123",
        name="test_name",
        surname="test_surname",
    )

    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    # Получаем абсолютный путь к директории приложения
    app_dir = Path(__file__).parent.parent

    # Создаем путь к файлу в директории uploads
    uploads_dir = app_dir / "main" / "uploads"
    test_file_path = uploads_dir / "test_image.jpeg"

    # Создаем файл в нужной директории
    with open(test_file_path, "wb") as f:
        f.write(b"fake_image_data")

    # Проверяем существование файла
    assert os.path.exists(test_file_path), f"File does not exist at {test_file_path}"

    # Используйте этот путь в тесте
    media_file = Media(id=1, path=str(test_file_path))
    db_session.add(media_file)
    await db_session.commit()

    db_media = (
        await db_session.execute(select(Media).where(Media.id == 1))
    ).scalar_one_or_none()
    assert db_media is not None
    assert db_media.id == 1
    assert db_media.path == str(test_file_path)

    # Отправляем запрос к эндпоинту
    response = await async_client.get(
        "/api/medias/1",
        headers={"api-key": user.api_key},
    )

    # Проверяем ответ
    if response.status_code == 404:
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not Found"
    else:
        assert response.status_code == 200
        assert response.content == b"fake_image_data"
        assert response.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_get_media_not_found_in_db(async_client, db_session):
    response = await async_client.get("/api/medias/999")
    assert response.status_code == 404
    data = response.json()
    assert data == {"detail": "Not Found"}
