import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory import Faker, SubFactory, post_generation
from sqlalchemy.ext.asyncio import AsyncSession
import random
import secrets
import string

from main.models import SubscribedUser, User, Tweet, LikeTweet, Media


class AsyncSQLAlchemyModelFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs):
        obj = cls.build(**kwargs)
        session.add(obj)
        await session.commit()
        return obj

    @classmethod
    async def create_batch(cls, session: AsyncSession, size: int, **kwargs):
        return [await cls.create(session, **kwargs) for _ in range(size)]


class UserFactory(AsyncSQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"

    name = Faker("first_name")
    surname = Faker("last_name")
    login = Faker("text", max_nb_chars=10)

    @post_generation
    def api_key(self, create, extracted, **kwargs):
        raw_key = extracted or "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(10)
        )
        self.set_api_key(raw_key)
        self._raw_api_key = raw_key



class TweetFactory(AsyncSQLAlchemyModelFactory):
    class Meta:
        model = Tweet
        sqlalchemy_session_persistence = "flush"

    user = SubFactory(UserFactory)
    content = Faker("text", max_nb_chars=500)  # Случайный текст
    attachments = factory.List(
        [factory.LazyFunction(lambda: random.randint(1, 100)) for _ in range(3)]
    )


# class LikeTweetFactory(AsyncSQLAlchemyModelFactory):
#     class Meta:
#         model = LikeTweet
#         sqlalchemy_session_persistence = "flush"
#
#     user = SubFactory(UserFactory)
#     tweet = SubFactory(TweetFactory)
#
#
# class SubscribedUserFactory(AsyncSQLAlchemyModelFactory):
#     class Meta:
#         model = SubscribedUser
#         sqlalchemy_session_persistence = "flush"
#
#     follower = SubFactory(UserFactory)
#     subscribed = SubFactory(UserFactory)
