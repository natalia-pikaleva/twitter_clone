from sqlalchemy import select
import pytest
from main.models import SubscribedUser, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_following(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id и api-key
    list_users = []
    for _ in range(5):
        factory_user = await UserFactory.create(session=db_session)
        list_users.append((factory_user.id, factory_user._raw_api_key))

    # Создадим подписки между пользователями
    for id_follow, api_key_follow in list_users:
        # Получаем пользователя из базы данных
        for id_subscribe, api_key_subscribe in list_users:
            if id_follow != id_subscribe:
                response = await async_client.post(
                    f"/api/users/{id_subscribe}/follow",
                    headers={"api-key": api_key_follow},
                )
                assert response.status_code == 201

                data = response.json()
                assert "result" in data
                assert data["result"] == "true"

                subscribe = (
                    await db_session.execute(
                        select(SubscribedUser).where(
                            SubscribedUser.follower_user_id == id_follow,
                            SubscribedUser.subscribed_user_id == id_subscribe,
                        )
                    )
                ).scalar()
                assert subscribe is not None


@pytest.mark.asyncio
async def test_following_invalid_api_key(async_client, db_session):
    # Создаём пользователя и фолловера
    user = await UserFactory.create(session=db_session)
    follower = await UserFactory.create(session=db_session)

    # Подписываем фолловера на пользователя, используя неверный api-key
    response = await async_client.post(
        f"/api/users/{user.id}/follow", headers={"api-key": "Invalid_api_key"}
    )

    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
        assert data["error_type"] == "ValueError"
    except:
        assert "Invalid API key" in response.text

    # Проверяем, что подписки в базе данных нет
    subscribe = (
        await db_session.execute(
            select(SubscribedUser).where(
                SubscribedUser.follower_user_id == follower.id,
                SubscribedUser.subscribed_user_id == user.id,
            )
        )
    ).scalar()
    assert subscribe is None


@pytest.mark.asyncio
async def test_following_invalid_id(async_client, db_session):
    # Создаём пользователя и фолловера
    user = await UserFactory.create(session=db_session)
    follower = await UserFactory.create(session=db_session)

    # Подписываем фолловера на пользователя, используя неверный id
    response = await async_client.post(
        f"/api/users/{user.id * 10}/follow", headers={"api-key": follower._raw_api_key}
    )

    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
        assert data["error_type"] == "ValueError"
    except:
        assert "Invalid API key" in response.text

    # Проверяем, что подписки в базе данных нет
    subscribe = (
        await db_session.execute(
            select(SubscribedUser).where(
                SubscribedUser.follower_user_id == follower.id,
                SubscribedUser.subscribed_user_id == user.id,
            )
        )
    ).scalar()
    assert subscribe is None
