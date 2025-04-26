from sqlalchemy import select
import pytest
from main.models import User, Tweet, SubscribedUser, LikeTweet
from .factories import UserFactory


@pytest.mark.asyncio
async def test__get_user_info(async_client, db_session):
    # Создаём пользователя
    user = await UserFactory.create(session=db_session)

    # Создаем еще несколько пользователей и сохраняем их id
    list_ids = []
    for index in range(6):
        factory_user = await UserFactory.create(session=db_session)
        list_ids.append(factory_user.id)

    # Создадим подписки нашего пользователя на часть других пользователей
    for subscribe_id in list_ids[:3]:
        subscribe = SubscribedUser(
            follower_user_id=user.id, subscribed_user_id=subscribe_id
        )
        db_session.add(subscribe)
        await db_session.flush()
        await db_session.refresh(subscribe)

    # Создадим подписки части других пользователей на нашего пользователя user
    for follower_id in list_ids[3:]:
        subscribe = SubscribedUser(
            follower_user_id=follower_id, subscribed_user_id=user.id
        )
        db_session.add(subscribe)
        await db_session.flush()
        await db_session.refresh(subscribe)

    # Получаем список подписчиков пользователя
    result = await db_session.execute(
        select(SubscribedUser).filter_by(subscribed_user_id=user.id)
    )
    followers = result.scalars().all()
    followers_ids = [follower.follower_user_id for follower in followers]

    # Получаем список подписок пользователя
    result = await db_session.execute(
        select(SubscribedUser).filter_by(follower_user_id=user.id)
    )
    following = result.scalars().all()
    following_ids = [follow.subscribed_user_id for follow in following]

    # Формируем информацию о пользователе
    user_info = {
        "id": user.id,
        "name": f"{user.name} {user.surname}",
        "followers": followers_ids,
        "following": following_ids,
    }

    # Делаем запрос на эндпоинт и сверяем полученную информацию
    response = await async_client.get(
        "/api/users/me", headers={"api-key": user._raw_api_key}
    )
    assert response.status_code == 200
    user_info_data = response.json()

    assert user_info_data["user"]["id"] == user_info["id"]
    assert user_info_data["user"]["name"] == user_info["name"]
    assert user_info_data["user"]["followers"] == user_info["followers"]
    assert user_info_data["user"]["following"] == user_info["following"]
