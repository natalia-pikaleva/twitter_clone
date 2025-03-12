from sqlalchemy import select

import pytest
from main.models import User, Tweet, Media


@pytest.mark.asyncio
async def test_delete_tweet(async_client, db_session):
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

    # Создаем твит
    tweet_user = Tweet(user_id=user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet_user)
    await db_session.flush()
    await db_session.refresh(tweet_user)

    # Проверяем, что твит создан
    tweet = (await db_session.execute(select(Tweet).where(Tweet.id == tweet_user.id))).scalar()
    assert tweet is not None

    # Удаляем созданный твит
    response = await async_client.delete(
        f"/api/tweets/{tweet_user.id}",
        headers={"api-key": user.api_key},
    )

    assert response.status_code == 200
    tweet_data = response.json()

    assert tweet_data["result"] == "true"

    # Проверяем, что твит удален
    tweet = (await db_session.execute(select(Tweet).where(Tweet.id == tweet_user.id))).scalar()
    assert tweet is None


@pytest.mark.asyncio
async def test_delete_tweet_invalid_api_key(async_client, db_session):
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

    # Создаем твит
    tweet_user = Tweet(user_id=user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet_user)
    await db_session.flush()
    await db_session.refresh(tweet_user)

    response = await async_client.delete(
        f"/api/tweets/{tweet_user.id}",
        headers={"api-key": "invalid_api_key"}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"

@pytest.mark.asyncio
async def test_delete_tweet_other_user(async_client, db_session):
    # Создаём двух пользователей
    first_user = User(
        login="first_test_login",
        api_key="first123",
        name="first_test_name",
        surname="first_test_surname",
    )

    second_user = User(
        login="second_test_login",
        api_key="second123",
        name="second_test_name",
        surname="second_test_surname",
    )

    db_session.add(first_user)
    db_session.add(second_user)
    await db_session.flush()
    await db_session.refresh(first_user)
    await db_session.refresh(second_user)


    # Создаем твит у второго пользователя
    tweet = Tweet(user_id=second_user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet)
    await db_session.flush()
    await db_session.refresh(tweet)

    # Пробуем удалить твит, используя api-key первого пользователя
    response = await async_client.delete(
        f"/api/tweets/{tweet.id}",
        headers={"api-key": first_user.api_key}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"
