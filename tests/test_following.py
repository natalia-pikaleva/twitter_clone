from sqlalchemy import select
import pytest
from main.models import SubscribedUser, User
from .factories import UserFactory


@pytest.mark.asyncio
async def test_following(async_client, db_session):
    # Создаем 5 пользователей и сохраняем их id
    list_ids = []
    for index in range(5):
        factory_user = await UserFactory.create(db_session)
        list_ids.append(factory_user.id)

    # Создадим подписки между пользователями
    for id_follow in list_ids:
        for id_subscribe in list_ids:
            if id_follow != id_subscribe:
                user = (
                    await db_session.execute(select(User).where(User.id == id_follow))
                ).scalar()
                response = await async_client.post(
                    f"/api/users/{id_subscribe}/follow",
                    headers={"api-key": user.api_key},
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
    user = User(
        login="test_login",
        api_key="123",
        name="test_name",
        surname="test_surname",
    )

    follower = User(
        login="test_login_follower",
        api_key="123follower",
        name="test_name_follower",
        surname="test_surname_follower",
    )

    db_session.add(user)
    db_session.add(follower)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.refresh(follower)

    # Подписываем фолловера на пользователя, используя неверный api-key
    response = await async_client.post(
        f"/api/users/{user.id}/follow", headers={"api-key": "Invalid_api_key"}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"

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
    user = User(
        login="test_login",
        api_key="123",
        name="test_name",
        surname="test_surname",
    )

    follower = User(
        login="test_login_follower",
        api_key="123follower",
        name="test_name_follower",
        surname="test_surname_follower",
    )

    db_session.add(user)
    db_session.add(follower)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.refresh(follower)

    # Подписываем фолловера на пользователя, используя неверный id
    response = await async_client.post(
        f"/api/users/{user.id * 10}/follow", headers={"api-key": follower.api_key}
    )

    assert response.status_code == 404
    data = response.json()

    assert data["result"] == "false"
    assert data["error_type"] == "ValueError"

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
