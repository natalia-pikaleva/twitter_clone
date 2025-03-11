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
                user = (await db_session.execute(select(User).where(User.id == id_follow))).scalar()
                response = await async_client.post(
                    f"/api/users/{id_subscribe}/follow",
                    headers={"api-key": user.api_key}
                )
                assert response.status_code == 201

                data = response.json()
                assert "result" in data
                assert data["result"] == "true"

                subscribe = (await db_session.execute(select(SubscribedUser).where(SubscribedUser.follower_user_id == id_follow, SubscribedUser.subscribed_user_id == id_subscribe))).scalar()
                assert subscribe is not None
