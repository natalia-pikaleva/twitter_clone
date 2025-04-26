from sqlalchemy import select

import pytest
from main.models import User, Tweet, Media
from .factories import UserFactory


@pytest.mark.asyncio
async def test_delete_tweet(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Создаем твит
    tweet_user = Tweet(user_id=user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet_user)
    await db_session.flush()
    await db_session.refresh(tweet_user)

    # Проверяем, что твит создан
    tweet = (
        await db_session.execute(select(Tweet).where(Tweet.id == tweet_user.id))
    ).scalar()
    assert tweet is not None

    # Удаляем созданный твит
    response = await async_client.delete(
        f"/api/tweets/{tweet_user.id}",
        headers={"api-key": user._raw_api_key},
    )

    assert response.status_code == 200
    tweet_data = response.json()

    assert tweet_data["result"] == "true"

    # Проверяем, что твит удален
    tweet = (
        await db_session.execute(select(Tweet).where(Tweet.id == tweet_user.id))
    ).scalar()
    assert tweet is None


@pytest.mark.asyncio
async def test_delete_tweet_invalid_api_key(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Создаем твит
    tweet_user = Tweet(user_id=user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet_user)
    await db_session.flush()
    await db_session.refresh(tweet_user)

    response = await async_client.delete(
        f"/api/tweets/{tweet_user.id}", headers={"api-key": "invalid_api_key"}
    )

    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
        assert data["error_type"] == "ValueError"
    except:
        assert "Invalid API key" in response.text


@pytest.mark.asyncio
async def test_delete_tweet_other_user(async_client, db_session):
    # Создаём двух пользователей
    first_user = await UserFactory.create(session=db_session)

    second_user = await UserFactory.create(session=db_session)

    # Создаем твит у второго пользователя
    tweet = Tweet(user_id=second_user.id, content=f"test_text_user", attachments=[])
    db_session.add(tweet)
    await db_session.flush()
    await db_session.refresh(tweet)

    # Пробуем удалить твит, используя api-key первого пользователя
    response = await async_client.delete(
        f"/api/tweets/{tweet.id}", headers={"api-key": first_user._raw_api_key}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"
