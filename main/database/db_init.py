import json

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
import logging
from main.models import Base, User, Tweet, LikeTweet
from sqlalchemy.exc import OperationalError
import csv
import os

SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://postgres:postgres@localhost:5432/twitter_db'

engine = create_engine(SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

session = Session()


def insert_users():
    """Заполнение таблицы пользователей"""
    try:
        logger.info("Start func insert_users")
        current_dir = os.path.dirname(__file__)
        users_file_path = os.path.join(current_dir, 'users.csv')

        if not os.path.exists(users_file_path):
            logger.warning("File users.csv does not exist")
            return

        with open(users_file_path, newline='', encoding='UTF-8') as csvfile:
            reader = csv.DictReader(csvfile)
            users_to_insert = []
            for row in reader:
                user = User(
                    id=row['id'],
                    login=row['login'],
                    api_key=row['api_key'],
                    name=row['name'],
                    surname=row['surname']
                )
                users_to_insert.append(user)
            session.bulk_save_objects(users_to_insert)
            session.commit()
            logger.info("Users inserted successfully")
    except Exception as e:
        logger.error(f"Error during insert users: {e}")



def insert_tweets_and_likes():
    """Заполнение таблиц твитов и лайков"""
    logger.info("Start func insert_tweets_and_likes")
    current_dir = os.path.dirname(__file__)
    tweets_file_path = os.path.join(current_dir, 'tweets.json')

    if not os.path.exists(tweets_file_path):
        logger.warning("File tweets.json does not exist")
        return

    try:
        with open(tweets_file_path, 'r', encoding='UTF-8') as tweets_file:
            data = json.load(tweets_file)
            logger.info(f"Loaded data: {data}")

            # Вставляем твиты
            tweets_to_insert = []
            for tweet in data.get("tweets", []):
                logger.info(f"Processing tweet: {tweet}")
                tweet_obj = Tweet(
                    user_id=tweet.get("user_id"),
                    content=tweet.get("content"),
                    attachments=tweet.get("attachments")
                )
                tweets_to_insert.append(tweet_obj)

            session.bulk_save_objects(tweets_to_insert)
            session.commit()
            logger.info("Tweets inserted successfully")

            # Вставляем лайки
            saved_tweets = session.query(Tweet).all()
            tweet_id_map = {t.content: t.id for t in saved_tweets}
            logger.info(f"Tweet ID map: {tweet_id_map}")

            likes_to_insert = []
            for tweet in data["tweets"]:
                logger.info(f"Processing tweet for likes: {tweet}")
                tweet_content = tweet.get("content")
                tweet_id = tweet_id_map.get(tweet_content)

                if not tweet_id:
                    logger.warning(f"Could not find tweet_id for content: {tweet_content}")
                    continue

                for user_id in tweet.get("likes_list", []):
                    logger.info(f"Processing like for user_id: {user_id}")
                    like_tweet = {"user_id": user_id, "tweet_id": tweet_id}
                    likes_to_insert.append(like_tweet)

            # Используем insert(...).on_conflict_do_nothing() для игнорирования дублирующихся строк
            stmt = insert(LikeTweet).values(likes_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=['user_id', 'tweet_id'])
            session.execute(stmt)
            session.commit()
            logger.info("Likes inserted successfully")

    except Exception as e:
        session.rollback()
        logger.error(f"Error during insert tweets and likes: {e}")
        raise



def check_db_exists(engine_url):
    try:
        engine = create_engine(engine_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Error checking database existence: {e}")
        return False


def start_bd():
    """
    Создание базы данных при старте
    """
    try:
        SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://postgres:postgres@localhost:5432/twitter_db'
        if not check_db_exists(SQLALCHEMY_DATABASE_URI):
            logger.info("Database does not exist. Creating...")

            import subprocess
            subprocess.run(f"psql -U postgres -c 'CREATE DATABASE twitter_db'", shell=True)
            logger.info("Database created successfully")

            global engine
            engine = create_engine(SQLALCHEMY_DATABASE_URI)
            global Session
            Session = sessionmaker(bind=engine)
            global session
            session = Session()

            logger.info("Start func start_bd")
            Base.metadata.reflect(bind=engine)
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
            logger.info("Tables created successfully")

            users = session.query(User).all()
            if not users:
                insert_users()
            else:
                logger.info("Table users is exists in database")

            tweets = session.query(Tweet).all()
            if not tweets:
                insert_tweets_and_likes()
            else:
                logger.info("Table tweets is exists in database")

    except OperationalError as e:
        logger.error(f"Operational error during database setup: {e}")
    except Exception as e:
        logger.error(f"Error during database setup: {e}")
