from sqlalchemy import select

import pytest
from main.models import User, Tweet, Media


@pytest.mark.asyncio
async def test_create_tweet_without_media(async_client, db_session):
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

    db_user = (await db_session.execute(select(User).where(User.api_key == "123"))).scalar()
    assert db_user is not None
    assert db_user.api_key == "123"

    response = await async_client.post(
        "/api/tweets",
        headers={"api-key": user.api_key},
        json={"tweet_data": "test text for tweet", "tweet_media_ids": []}
    )

    assert response.status_code == 201
    tweet_data = response.json()

    assert tweet_data["result"] == "true"
    assert tweet_data["tweet_id"] is not None

    tweet = (await db_session.execute(select(Tweet).where(Tweet.id == tweet_data["tweet_id"]))).scalar()
    assert tweet is not None
    assert tweet.content == "test text for tweet"


@pytest.mark.asyncio
async def test_create_tweet_with_media(async_client, db_session):
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

    db_user = (await db_session.execute(select(User).where(User.api_key == "123"))).scalar()
    assert db_user is not None
    assert db_user.api_key == "123"

    # Создаём тестовый файл
    file_path = "tests/test_image.jpeg"
    with open(file_path, "rb") as file:
        files = {"file": (file_path, file, "image/jpeg")}

        # Отправляем запрос с файлом
        response = await async_client.post(
            "/api/medias",
            headers={"api-key": user.api_key},
            files=files  # Передаём файл через параметр files
        )

    assert response.status_code == 200

    # Проверяем, что файл сохранен в базе данных
    media = (await db_session.execute(select(Media))).scalars().first()
    assert media is not None

    media_id = response.json()["media_id"]

    response = await async_client.post(
        "/api/tweets",
        headers={"api-key": user.api_key},
        json={"tweet_data": "test text for tweet", "tweet_media_ids": [media_id]}
    )

    assert response.status_code == 201
    tweet_data = response.json()

    assert tweet_data["result"] == "true"
    assert tweet_data["tweet_id"] is not None

    tweet = (await db_session.execute(select(Tweet).where(Tweet.id == tweet_data["tweet_id"]))).scalar()
    assert tweet is not None
    assert tweet.content == "test text for tweet"
    assert media_id in tweet.attachments

@pytest.mark.asyncio
async def test_create_tweet_invalid_api_key(async_client, db_session):
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

    db_user = (await db_session.execute(select(User).where(User.api_key == "123"))).scalar()
    assert db_user is not None
    assert db_user.api_key == "123"

    response = await async_client.post(
        "/api/tweets",
        headers={"api-key": "invalid_api_key"},
        json={"tweet_data": "test text for tweet", "tweet_media_ids": []}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"
