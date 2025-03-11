from sqlalchemy import select
import random
import pytest
from main.models import Tweet, SubscribedUser, LikeTweet, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_get_tweets(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id
    list_ids = []
    for index in range(5):
        factory_user = await UserFactory.create(db_session)
        list_ids.append(factory_user.id)

    # Создадим у каждого пользователя случайное количество твитов
    for user_id in list_ids:
        count_tweets = random.randint(1, 5)  # Убедитесь, что хотя бы один твит создается
        for index in range(count_tweets):
            tweet = Tweet(user_id=user_id, content=f"test_text_{user_id} {index}", attachments=[])
            db_session.add(tweet)
            await db_session.flush()
            await db_session.refresh(tweet)

    # Создадим подписки между пользователями
    for i in range(len(list_ids)):
        for j in range(i + 1, len(list_ids)):
            if random.random() < 0.5:  # Подписываемся с вероятностью 50%
                subscription = SubscribedUser(
                    follower_user_id=list_ids[i],
                    subscribed_user_id=list_ids[j]
                )
                db_session.add(subscription)
                await db_session.flush()
                await db_session.refresh(subscription)


    # Создадим лайки для твитов
    tweets = (await db_session.execute(select(Tweet))).scalars().all()
    for tweet in tweets:
        if random.random() < 0.5:  # Лайкаем с вероятностью 50%
            like = LikeTweet(user_id=random.choice(list_ids), tweet_id=tweet.id)
            db_session.add(like)
            await db_session.flush()
            await db_session.refresh(like)

    # Проверяем эндпоинт для каждого пользователя
    for user_id in list_ids:
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar()
        response = await async_client.get(
            "/api/tweets",
            headers={"api-key": user.api_key}
        )
        assert response.status_code == 200

        tweets_data = response.json()
        assert "result" in tweets_data
        assert "tweets" in tweets_data

        # Проверяем, что все твиты пользователя в ответе
        user_tweets = (await db_session.execute(select(Tweet).where(Tweet.user_id == user_id))).scalars().all()
        for tweet in user_tweets:
            assert any(t["id"] == tweet.id for t in tweets_data["tweets"])