from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models import User, Twit, LikeTwit, SubscribedUser
from db_init import session


def get_user_by_id(user_id):
    """Поиск пользователя по его id"""

    user = session.query(User).filter_by(id=user_id).first()
    session.close()
    return user

def add_user(user_data):
    """Добавление пользователя в базу данных"""

    new_user = User(**user_data)
    session.add(new_user)
    session.commit()
    session.close()

