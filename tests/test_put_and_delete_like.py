from sqlalchemy import select
import random
import pytest
from main.models import Tweet, SubscribedUser, LikeTweet, User
from .factories import UserFactory
from sqlalchemy.sql.expression import or_


@pytest.mark.asyncio
async def test_put_and_delete_likes(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id и api-key
    list_users = []
    for _ in range(5):
        factory_user = await UserFactory.create(session=db_session)
        list_users.append((factory_user.id, factory_user._raw_api_key))

    # Создадим у каждого пользователя случайное количество твитов, сохраним их id
    list_tweets_ids = []
    for user_id, api_key_user in list_users:
        count_tweets = random.randint(
            1, 5
        )  # Убедитесь, что хотя бы один твит создается
        for index in range(count_tweets):
            tweet = Tweet(
                user_id=user_id, content=f"test_text_{user_id} {index}", attachments=[]
            )
            db_session.add(tweet)
            await db_session.flush()
            await db_session.refresh(tweet)
            list_tweets_ids.append(tweet.id)

    # Создадим лайки для каждого пользователя
    for user_id, api_key_user in list_users:
        for tweet_id in list_tweets_ids:
            response = await async_client.post(
                f"/api/tweets/{tweet_id}/likes", headers={"api-key": api_key_user}
            )
            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"] == "true"

            db_like_tweet = (
                await db_session.execute(
                    select(LikeTweet).where(
                        LikeTweet.tweet_id == tweet_id, LikeTweet.user_id == user_id
                    )
                )
            ).scalar()

            assert db_like_tweet is not None

    # Удалим все лайки для каждого пользователя
    for user_id, api_key_user in list_users:
        for tweet_id in list_tweets_ids:
            response = await async_client.post(
                f"/api/tweets/{tweet_id}/likes", headers={"api-key": api_key_user}
            )
            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"] == "true"

            db_like_tweet = (
                await db_session.execute(
                    select(LikeTweet).where(
                        LikeTweet.tweet_id == tweet_id, LikeTweet.user_id == user_id
                    )
                )
            ).scalar()

            assert db_like_tweet is None


@pytest.mark.asyncio
async def test_put_likes_invalid_api_key(async_client, db_session):
    # Создаём двух пользователей
    first_user = await UserFactory.create(session=db_session)
    second_user = await UserFactory.create(session=db_session)

    # У каждого пользователя создаем по одному твиту
    tweet_first_user = Tweet(
        user_id=first_user.id, content=f"test_text_first_user", attachments=[]
    )
    tweet_second_user = Tweet(
        user_id=second_user.id, content=f"test_text_second_user", attachments=[]
    )
    db_session.add(tweet_first_user)
    db_session.add(tweet_second_user)
    await db_session.flush()
    await db_session.refresh(tweet_first_user)
    await db_session.refresh(tweet_second_user)

    # Пробуем поставить лайки на твиты используя неверный api-key
    response = await async_client.post(
        f"/api/tweets/{tweet_first_user.id}/likes",
        headers={"api-key": "Invalid_api_key"},
    )
    assert response.status_code == 404

    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
        assert data["error_type"] == "ValueError"
    except:
        assert "Invalid API key" in response.text

    response = await async_client.post(
        f"/api/tweets/{tweet_second_user.id}/likes",
        headers={"api-key": "Invalid_api_key"},
    )
    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
        assert data["error_type"] == "ValueError"
    except:
        assert "Invalid API key" in response.text

    # Проверяем, что лайков в базе данных нет
    db_like_tweet = (
        await db_session.execute(
            select(LikeTweet).where(
                or_(
                    LikeTweet.tweet_id == tweet_first_user.id,
                    LikeTweet.tweet_id == tweet_second_user.id,
                ),
                LikeTweet.user_id == first_user.id,
            )
        )
    ).all()

    assert db_like_tweet == []


@pytest.mark.asyncio
async def test_put_likes_invalid_tweet_id(async_client, db_session):
    # Создаём двух пользователей
    first_user = await UserFactory.create(session=db_session)
    second_user = await UserFactory.create(session=db_session)

    # У каждого пользователя создаем по одному твиту
    tweet_first_user = Tweet(
        user_id=first_user.id, content=f"test_text_first_user", attachments=[]
    )
    tweet_second_user = Tweet(
        user_id=second_user.id, content=f"test_text_second_user", attachments=[]
    )
    db_session.add(tweet_first_user)
    db_session.add(tweet_second_user)
    await db_session.flush()
    await db_session.refresh(tweet_first_user)
    await db_session.refresh(tweet_second_user)

    # Пробуем поставить лайки на твиты используя неверный id твитов
    response = await async_client.post(
        f"/api/tweets/{tweet_first_user.id * 10}/likes",
        headers={"api-key": first_user._raw_api_key},
    )
    assert response.status_code == 404

    data = response.json()
    assert "result" in data
    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"

    response = await async_client.post(
        f"/api/tweets/{tweet_second_user.id * 10}/likes",
        headers={"api-key": first_user._raw_api_key},
    )
    assert response.status_code == 404

    data = response.json()
    assert "result" in data
    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"

    # Проверяем, что лайков в базе данных нет
    db_like_tweet = (
        await db_session.execute(
            select(LikeTweet).where(
                or_(
                    LikeTweet.tweet_id == tweet_first_user.id,
                    LikeTweet.tweet_id == tweet_second_user.id,
                ),
                LikeTweet.user_id == first_user.id,
            )
        )
    ).all()

    assert db_like_tweet == []
