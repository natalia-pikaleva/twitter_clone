from sqlalchemy import select
import pytest
from main.models import SubscribedUser, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_unfollowing(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id и api-key
    list_users = []
    for _ in range(5):
        factory_user = await UserFactory.create(session=db_session)
        list_users.append((factory_user.id, factory_user._raw_api_key))

    # Создадим подписки между пользователями
    for id_follow, api_key_follow in list_users:
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

    # Удалим подписки между пользователями
    for id_follow, api_key_follow in list_users:
        for id_subscribe, api_key_subscribe in list_users:
            if id_follow != id_subscribe:
                user = (
                    await db_session.execute(select(User).where(User.id == id_follow))
                ).scalar()
                response = await async_client.delete(
                    f"/api/users/{id_subscribe}/follow",
                    headers={"api-key": api_key_follow},
                )
                assert response.status_code == 200

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
                assert subscribe is None


@pytest.mark.asyncio
async def test_unfollowing_invalid_api_key(async_client, db_session):
    # Создаём пользователя и фолловера
    user = await UserFactory.create(session=db_session)
    follower = await UserFactory.create(session=db_session)

    # Подписываем фолловера на пользователя
    response = await async_client.post(
        f"/api/users/{user.id}/follow", headers={"api-key": follower._raw_api_key}
    )

    assert response.status_code == 201

    data = response.json()
    assert "result" in data
    assert data["result"] == "true"

    # Проверяем, что подписка в базе данных есть
    subscribe = (
        await db_session.execute(
            select(SubscribedUser).where(
                SubscribedUser.follower_user_id == follower.id,
                SubscribedUser.subscribed_user_id == user.id,
            )
        )
    ).scalar()
    assert subscribe is not None

    # Отписываемся от пользователя, но используем неверный api-key
    response = await async_client.delete(
        f"/api/users/{user.id}/follow", headers={"api-key": "invalid_api_key"}
    )

    assert response.status_code in (401, 403, 404)
    try:
        data = response.json()
        assert "result" in data
        assert data["result"] == "false"
    except:
        assert "Invalid API key" in response.text


@pytest.mark.asyncio
async def test_unfollowing_invalid_id(async_client, db_session):
    # Создаём пользователя и фолловера
    user = await UserFactory.create(session=db_session)
    follower = await UserFactory.create(session=db_session)

    # Подписываем фолловера на пользователя
    response = await async_client.post(
        f"/api/users/{user.id}/follow", headers={"api-key": follower._raw_api_key}
    )

    assert response.status_code == 201

    data = response.json()
    assert "result" in data
    assert data["result"] == "true"

    # Проверяем, что подписка в базе данных есть
    subscribe = (
        await db_session.execute(
            select(SubscribedUser).where(
                SubscribedUser.follower_user_id == follower.id,
                SubscribedUser.subscribed_user_id == user.id,
            )
        )
    ).scalar()
    assert subscribe is not None

    # Отписываемся от пользователя, но используем неверный id пользователя
    response = await async_client.delete(
        f"/api/users/{user.id * 10}/follow", headers={"api-key": follower._raw_api_key}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"
