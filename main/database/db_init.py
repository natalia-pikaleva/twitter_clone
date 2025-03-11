import asyncio
import csv
import json
import logging
import os
from typing import List, AsyncGenerator


import asyncpg
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from main.models import Base, LikeTweet, Media, SubscribedUser, Tweet, User

SQLALCHEMY_DATABASE_URI = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/twitter_db"
)

# engine = create_async_engine(SQLALCHEMY_DATABASE_URI, echo=True)
engine = create_async_engine(SQLALCHEMY_DATABASE_URI)

AsyncSessionLocal = sessionmaker(engine,
                                 expire_on_commit=False,
                                 class_=AsyncSession)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - "
                              "%(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async session"""
    async with AsyncSessionLocal() as session:
        yield session


async def insert_users(session: AsyncSession) -> None:
    """Заполнение таблицы пользователей"""
    try:
        logger.info("Start func insert_users")
        current_dir = os.path.dirname(__file__)
        users_file_path = os.path.join(current_dir, "users.csv")

        if not os.path.exists(users_file_path):
            logger.warning("File users.csv does not exist")
            return

        with open(users_file_path, newline="", encoding="UTF-8") as csvfile:
            reader = csv.DictReader(csvfile)
            users_to_insert = []
            for row in reader:
                user = User(
                    login=row["login"],
                    api_key=row["api_key"],
                    name=row["name"],
                    surname=row["surname"],
                )
                users_to_insert.append(user)
            session.add_all(users_to_insert)
            await session.commit()
            logger.info("Users inserted successfully")
    except Exception as e:
        logger.error(f"Error during insert users: {e}")
        await session.rollback()


async def insert_following(session: AsyncSession) -> None:
    """Заполнение таблицы подписчиков"""
    logger.info("Start func insert_following")
    current_dir = os.path.dirname(__file__)
    following_file_path = os.path.join(current_dir, "following.json")

    if not os.path.exists(following_file_path):
        logger.warning("File following.json does not exist")
        return

    try:
        with (open(following_file_path, "r", encoding="UTF-8")
              as following_file):
            data = json.load(following_file)
            logger.info(f"Loaded data: {data}")

            # Вставляем подписки
            subscribes_to_insert = []
            for follower in data.get("following", []):
                logger.info(f"Processing following: {follower}")
                for sub_id in follower["subscribed_list"]:
                    subscribe_obj = SubscribedUser(
                        follower_user_id=follower.get("follower_id"),
                        subscribed_user_id=sub_id,
                    )
                    subscribes_to_insert.append(subscribe_obj)

            session.add_all(subscribes_to_insert)
            await session.commit()
            logger.info("Subscribs inserted successfully")

    except Exception as e:
        await session.rollback()
        logger.error(f"Error during insert tweets and likes: {e}")
        raise


async def load_tweets_data(file_path: str) -> dict:
    """Загрузка данных из файла tweets.json"""
    try:
        with open(file_path, "r", encoding="UTF-8") as tweets_file:
            return json.load(tweets_file)
    except Exception as e:
        logger.error(f"Error loading tweets data: {e}")
        return {}


async def insert_media(
        session: AsyncSession,
        UPLOAD_FOLDER_ABSOLUTE: str,
        attachments_list: List[str]
) -> List[int]:
    """Вставка медиа в базу данных"""
    media_ids = []
    for filename in attachments_list:
        filepath = os.path.join(UPLOAD_FOLDER_ABSOLUTE, filename)
        media = Media(path=filepath)
        session.add(media)
        await session.commit()
        await session.refresh(media)
        media_ids.append(media.id)
        logger.info("Media saved in db")
    return media_ids


async def insert_tweets(
    session: AsyncSession, data: dict, UPLOAD_FOLDER_ABSOLUTE: str
) -> None:
    """Вставка твитов в базу данных"""
    tweets_to_insert = []
    for tweet in data.get("tweets", []):
        logger.info(f"Processing tweet: {tweet}")
        attachments_list = tweet.get("attachments")
        media_ids = await insert_media(
            session, UPLOAD_FOLDER_ABSOLUTE, attachments_list
        )

        tweet_obj = Tweet(
            user_id=tweet.get("user_id"),
            content=tweet.get("content"),
            attachments=media_ids,
        )
        tweets_to_insert.append(tweet_obj)

    session.add_all(tweets_to_insert)
    try:
        await session.commit()
        logger.info("Tweets inserted successfully")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Error inserting tweets: {e}")


async def insert_likes(session: AsyncSession, data: dict) -> None:
    """Вставка лайков в базу данных"""
    result = await session.execute(select(Tweet))
    saved_tweets = result.scalars().all()
    tweet_id_map = {t.content: t.id for t in saved_tweets}
    logger.info(f"Tweet ID map: {tweet_id_map}")

    likes_to_insert = []
    for tweet in data["tweets"]:
        logger.info(f"Processing tweet for likes: {tweet}")
        tweet_content = tweet.get("content")
        tweet_id = tweet_id_map.get(tweet_content)

        if not tweet_id:
            logger.warning(f"Could not find tweet_id for content: "
                           f"{tweet_content}")
            continue

        for user_id in tweet.get("likes_list", []):
            logger.info(f"Processing like for user_id: {user_id}")
            like_tweet = {"user_id": user_id, "tweet_id": tweet_id}
            likes_to_insert.append(like_tweet)

    stmt = insert(LikeTweet).values(likes_to_insert)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "tweet_id"])
    try:
        await session.execute(stmt)
        await session.commit()
        logger.info("Likes inserted successfully")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Error inserting likes: {e}")


async def insert_tweets_and_likes(
    session: AsyncSession, UPLOAD_FOLDER_ABSOLUTE: str
) -> None:
    """Заполнение таблиц твитов и лайков"""
    logger.info("Start func insert_tweets_and_likes")
    current_dir = os.path.dirname(__file__)
    tweets_file_path = os.path.join(current_dir, "tweets.json")

    if not os.path.exists(tweets_file_path):
        logger.warning("File tweets.json does not exist")
        return

    data = await load_tweets_data(tweets_file_path)
    if not data:
        logger.warning("No data loaded from tweets.json")
        return

    logger.info(f"Loaded data: {data}")

    await insert_tweets(session, data, UPLOAD_FOLDER_ABSOLUTE)
    await insert_likes(session, data)


async def check_db_exists(db_url: str) -> bool:
    """Проверка существования БД через asyncpg"""
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="postgres",
            host="localhost",
            database=db_url.split("/")[-1],
        )
        await conn.close()
        return True
    except asyncpg.InvalidCatalogNameError:
        return False
    except Exception as e:
        logger.error(f"Error checking database existence: {e}")
        return False


async def create_database(db_name: str) -> bool:
    """Создание БД с помощью asyncpg"""
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="postgres",
            host="localhost",
            database="postgres",
        )
        await conn.execute(f"CREATE DATABASE {db_name}")
        await conn.close()
        logger.info(f"Database {db_name} created successfully")
        return True
    except asyncpg.exceptions.DuplicateDatabaseError:
        logger.warning(f"Database {db_name} already exists")
        return True
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False


async def drop_database(db_name) -> None:
    """
    Удаление базы данных.
    """
    try:
        conn = await asyncpg.connect(
            host="localhost", port=5432, user="postgres", password="postgres"
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {db_name};")
        await conn.close()
        logger.info(f"Database {db_name} dropped successfully")
    except asyncpg.exceptions.DatabaseError as e:
        logger.error(f"Failed to drop database: {e}")


async def start_bd(UPLOAD_FOLDER_ABSOLUTE) -> None:
    """
    Создание базы данных при старте
    """
    try:
        SQLALCHEMY_DATABASE_URI = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/twitter_db"
        )
        db_name = "twitter_db"

        # Удаление базы данных, если она существует
        # await drop_database(db_name)
        # await asyncio.sleep(1)

        if not await check_db_exists(SQLALCHEMY_DATABASE_URI):
            logger.info("Database does not exist. Creating...")

            if not await create_database(db_name):
                logger.error("Failed to create database. Exiting.")
                return
            await asyncio.sleep(1)

            global engine
            engine = create_async_engine(SQLALCHEMY_DATABASE_URI, echo=True)

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables created successfully")

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()

                if not users:
                    await insert_users(session)
                else:
                    logger.info("Table users is exists in database")

                result = await session.execute(select(Tweet))
                tweets = result.scalars().all()
                if not tweets:
                    await insert_tweets_and_likes(session,
                                                  UPLOAD_FOLDER_ABSOLUTE)
                else:
                    logger.info("Table tweets is exists in database")

                result = await session.execute(select(SubscribedUser))
                subscribes = result.scalars().all()
                if not subscribes:
                    await insert_following(session)
                else:
                    logger.info("Table subscribed_users is exists in database")

            await engine.dispose()

    except OperationalError as e:
        logger.error(f"Operational error during database setup: {e}")
    except Exception as e:
        logger.error(f"Error during database setup: {e}")


