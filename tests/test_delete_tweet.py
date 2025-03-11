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

    # Создаем твит
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

    response = await async_client.delete(
        f"/api/tweets/{tweet.id}",
        headers={"api-key": user.api_key}
    )

    assert response.status_code == 200
    assert response.json()["result"] == "true"


    tweet = (await db_session.execute(select(Tweet).where(Tweet.id == tweet.id))).scalar()
    assert tweet is None

