from sqlalchemy import select
import random
import pytest
from main.models import Tweet, SubscribedUser, LikeTweet, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_get_tweets(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id
    list_users = []
    for _ in range(5):
        factory_user = await UserFactory.create(session=db_session)
        list_users.append((factory_user.id, factory_user._raw_api_key))

    # Создадим у каждого пользователя случайное количество твитов
    for user_id, _ in list_users:
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

    # Создадим подписки между пользователями
    for i in range(len(list_users)):
        for j in range(i + 1, len(list_users)):
            if random.random() < 0.5:  # Подписываемся с вероятностью 50%
                follower_user_id, _ = list_users[i]
                subscribed_user_id, _ = list_users[j]
                subscription = SubscribedUser(
                    follower_user_id=follower_user_id, subscribed_user_id=subscribed_user_id
                )
                db_session.add(subscription)
                await db_session.flush()
                await db_session.refresh(subscription)

    # Создадим лайки для твитов
    tweets = (await db_session.execute(select(Tweet))).scalars().all()
    for tweet in tweets:
        if random.random() < 0.5:  # Лайкаем с вероятностью 50%
            random_user = random.choice(list_users)  # Выбираем случайный кортеж (id, api_key)
            user_id, api_key = random_user
            like = LikeTweet(user_id=user_id, tweet_id=tweet.id)
            db_session.add(like)
            await db_session.flush()
            await db_session.refresh(like)

    # Проверяем эндпоинт для каждого пользователя
    for user_id, api_key_user in list_users:

        response = await async_client.get(
            "/api/tweets", headers={"api-key":api_key_user}
        )
        assert response.status_code == 200

        tweets_data = response.json()
        assert "result" in tweets_data
        assert "tweets" in tweets_data

        # Проверяем, что все твиты пользователя в ответе
        user_tweets = (
            (await db_session.execute(select(Tweet).where(Tweet.user_id == user_id)))
            .scalars()
            .all()
        )
        for tweet in user_tweets:
            assert any(t["id"] == tweet.id for t in tweets_data["tweets"])
