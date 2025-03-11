from sqlalchemy import select
import random
import pytest
from main.models import Tweet, SubscribedUser, LikeTweet, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_put_and_delete_likes(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id
    list_ids = []
    for index in range(5):
        factory_user = await UserFactory.create(db_session)
        list_ids.append(factory_user.id)

    # Создадим у каждого пользователя случайное количество твитов, сохраним их id
    list_tweets_ids = []
    for user_id in list_ids:
        count_tweets = random.randint(1, 5)  # Убедитесь, что хотя бы один твит создается
        for index in range(count_tweets):
            tweet = Tweet(user_id=user_id, content=f"test_text_{user_id} {index}", attachments=[])
            db_session.add(tweet)
            await db_session.flush()
            await db_session.refresh(tweet)
            list_tweets_ids.append(tweet.id)



    # Создадим лайки для каждого пользователя
    for user_id in list_ids:
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar()

        for tweet_id in list_tweets_ids:
            response = await async_client.post(
                f"/api/tweets/{tweet_id}/likes",
                headers={"api-key": user.api_key}
            )
            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"] == "true"

            db_like_tweet = (await db_session.execute(select(LikeTweet).where(LikeTweet.tweet_id == tweet_id, LikeTweet.user_id == user_id))).scalar()

            assert db_like_tweet is not None

    # Удалим все лайки для каждого пользователя
    for user_id in list_ids:
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar()

        for tweet_id in list_tweets_ids:
            response = await async_client.post(
                f"/api/tweets/{tweet_id}/likes",
                headers={"api-key": user.api_key}
            )
            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"] == "true"

            db_like_tweet = (await db_session.execute(
                select(LikeTweet).where(LikeTweet.tweet_id == tweet_id, LikeTweet.user_id == user_id))).scalar()

            assert db_like_tweet is None