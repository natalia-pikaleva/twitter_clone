from flask import jsonify
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from typing import Dict, Any

Base = declarative_base()


class SubscribedUser(Base):
    __tablename__ = 'subscribed_users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    follower_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subscribed_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('follower_user_id', 'subscribed_user_id', name='unique_user_subscribed'),
    )

    follower = relationship("User", foreign_keys=[follower_user_id], back_populates="follower", lazy='selectin')
    subscribed = relationship("User", foreign_keys=[subscribed_user_id], back_populates="subscribed_to",
                              lazy='selectin')

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "follower_user_id": self.follower_user_id,
            "subscribed_user_id": self.subscribed_user_id
        }


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    login = Column(String(50), nullable=False)
    api_key = Column(String(50), nullable=False)
    name = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)

    tweet = relationship("Tweet", back_populates="user", cascade="all, delete-orphan", lazy='subquery')
    follower = relationship("SubscribedUser", foreign_keys=[SubscribedUser.subscribed_user_id],
                            back_populates="subscribed", lazy='selectin')
    subscribed_to = relationship("SubscribedUser", foreign_keys=[SubscribedUser.follower_user_id],
                                 back_populates="follower", lazy='selectin')
    liked_tweets = relationship("LikeTweet", back_populates="user", cascade="all, delete-orphan", lazy='selectin')

    __table_args__ = (
        UniqueConstraint('api_key', name='unique_api_key'),)

    def __repr__(self):
        return f"Пользователь {self.name} {self.surname} @{self.login}"

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "login": self.login,
            "name": self.name,
            "surname": self.surname
        }


class Tweet(Base):
    __tablename__ = 'tweets'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    user_id = Column(Integer(), ForeignKey("users.id"), nullable=False)
    content = Column(String(500), nullable=False, default="")
    attachments = Column(ARRAY(String))

    user = relationship("User", back_populates="tweet")
    liked_by = relationship("LikeTweet", back_populates="tweet", cascade="all, delete-orphan", lazy='selectin')

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "attachments": self.attachments
        }


class LikeTweet(Base):
    __tablename__ = 'liking_tweets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tweet_id = Column(Integer, ForeignKey('tweets.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'tweet_id', name='unique_like_user_tweet'),
    )

    user = relationship("User", back_populates="liked_tweets", lazy='selectin')
    tweet = relationship("Tweet", back_populates="liked_by", lazy='selectin')

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tweet_id": self.tweet_id
        }
