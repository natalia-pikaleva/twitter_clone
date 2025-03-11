from sqlalchemy import select

import pytest
from main.models import User, Tweet


@pytest.mark.asyncio
async def test_get_user_info(async_client, db_session):
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

    response = await async_client.get(
        "/api/users/me",
        headers={"api-key": user.api_key}
    )
    assert response.status_code == 200
    user_info_data = response.json()

    assert user_info_data["user"]["id"] == user.id
    assert user_info_data["user"]["name"] == f"{user.name} {user.surname}"

