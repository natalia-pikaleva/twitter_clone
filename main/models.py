from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base, relationship
import bcrypt

Base = declarative_base()


class SubscribedUser(Base):
    __tablename__ = "subscribed_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    follower_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscribed_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "follower_user_id", "subscribed_user_id", name="unique_user_subscribed"
        ),
    )

    follower = relationship(
        "User",
        foreign_keys=[follower_user_id],
        back_populates="follower",
        lazy="selectin",
    )
    subscribed = relationship(
        "User",
        foreign_keys=[subscribed_user_id],
        back_populates="subscribed_to",
        lazy="selectin",
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    login = Column(String(50), nullable=False, unique=True)  # Изменено
    _api_key_hash = Column("api_key", String(255), index=True)
    name = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)

    @property
    def api_key(self):
        raise AttributeError("Доступ к API-ключу запрещен")

    def set_api_key(self, raw_key: str):
        self._api_key_hash = bcrypt.hashpw(
            raw_key.encode(),
            bcrypt.gensalt()
        ).decode()

    def verify_api_key(self, raw_key: str) -> bool:
        if not hasattr(self, '_api_key_hash') or not self._api_key_hash:
            return False
        try:
            return bcrypt.checkpw(
                raw_key.encode(),
                self._api_key_hash.encode()
            )
        except (ValueError, AttributeError):
            return False

    __table_args__ = (
        UniqueConstraint("api_key", name="unique_api_key"),
    )

    tweet = relationship(
        "Tweet", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    follower = relationship(
        "SubscribedUser",
        foreign_keys=[SubscribedUser.subscribed_user_id],
        back_populates="subscribed",
        lazy="selectin",
    )
    subscribed_to = relationship(
        "SubscribedUser",
        foreign_keys=[SubscribedUser.follower_user_id],
        back_populates="follower",
        lazy="selectin",
    )
    liked_tweets = relationship(
        "LikeTweet",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Tweet(Base):
    __tablename__ = "tweets"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    user_id = Column(Integer(), ForeignKey("users.id"), nullable=False)
    content = Column(String(500), nullable=False, default="")
    attachments = Column(ARRAY(Integer))

    user = relationship("User", back_populates="tweet")
    liked_by = relationship(
        "LikeTweet",
        back_populates="tweet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LikeTweet(Base):
    __tablename__ = "liking_tweets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tweet_id = Column(Integer, ForeignKey("tweets.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "tweet_id", name="unique_like_user_tweet"),
    )

    user = relationship("User", back_populates="liked_tweets", lazy="selectin")
    tweet = relationship("Tweet", back_populates="liked_by", lazy="selectin")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    path = Column(String(500), nullable=False, default="")
