from sqlalchemy.exc import NoResultFound

from main.models import User, Tweet, LikeTweet, SubscribedUser
from .db_init import session
import logging
from flask import jsonify
from typing import List
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


def get_tweets_by_user_api_key(api_key):
    """Поиск твитов пользователя по его id"""
    try:
        user = session.query(User).filter_by(api_key=api_key).one()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        user_id = user.id

        tweets = session.query(Tweet).all()

        data_tweets = []
        for tweet in tweets:
            likes_list = session.query(LikeTweet).filter_by(tweet_id=tweet.id).all()
            author = tweet.user

            likes_ids = [like.user_id for like in likes_list]
            data_tweet = {"id": tweet.id, "content": tweet.content, "attachments": tweet.attachments,
                          "author": {"id": author.id, "name": f"{author.name} {author.surname}"}, "likes": likes_ids}
            data_tweets.append(data_tweet)

        result = {"result": "true", "tweets": data_tweets}
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error during get tweets of user: {e}")
        data = {"result": "false", "error_type": "Invalid tweets",
                "error_message": e}
        return jsonify(data), 400
    finally:
        session.close()


def get_user_by_api_key(api_key):
    """Получение информации о пользователе по его api-key"""
    try:
        user = session.query(User).filter_by(api_key=api_key).first()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        subscribed_users = session.query(SubscribedUser).filter_by(follower_user_id=user.id).all()
        subscribed_user_ids = [su.subscribed_user_id for su in subscribed_users]

        # Используем JOIN для эффективного запроса
        subscribed_users_data = session.query(User.id, User.name, User.surname).join(
            SubscribedUser, User.id == SubscribedUser.subscribed_user_id
        ).filter(SubscribedUser.follower_user_id == user.id).all()

        following_data = [{"id": sub[0], "name": f"{sub[1]} {sub[2]}"} for sub in subscribed_users_data]

        # Получаем пользователей, которые подписаны на пользователя
        following_users = session.query(SubscribedUser).filter_by(subscribed_user_id=user.id).all()
        following_user_ids = [fo.follower_user_id for fo in following_users]

        # Используем JOIN для эффективного запроса
        followers_data_query = session.query(User.id, User.name, User.surname).join(
            SubscribedUser, User.id == SubscribedUser.follower_user_id
        ).filter(SubscribedUser.subscribed_user_id == user.id).all()

        followers_data = [{"id": fo[0], "name": f"{fo[1]} {fo[2]}"} for fo in followers_data_query]
        data_user = {"id": user.id, "name": f"{user.name} {user.surname}", "followers": followers_data,
                     "following": following_data}

        result = {"result": "true", "user": data_user}
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error during get user infor: {e}")
        data = {"result": "false", "error_type": "Invalid user info",
                "error_message": e}
        return jsonify(data), 400
    finally:
        session.close()


def put_or_delete_like_on_tweet(api_key: str, tweet_id: int):
    """Пользователь с данным api-key ставит лайк на твит с tweet_id"""
    try:
        user = session.query(User).filter_by(api_key=api_key).first()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        tweet = session.query(Tweet).filter_by(id=tweet_id).one()
        if tweet is None:
            logger.error(f"tweet with id {tweet_id} do not found")
            data = {"result": "false", "error_type": "invalid tweet id",
                    "error_message": "tweet with tweet_id do not found"}
            return jsonify(data), 400

        # Пытаемся получить существующий лайк
        like_tweet = session.query(LikeTweet).filter_by(user_id=user.id, tweet_id=tweet_id).first()
        if like_tweet is None:  # лайк не существует, устанавливаем его
            logger.info(f"Like do not exist for user {user.id} on tweet {tweet_id}")
            like_tweet = LikeTweet(tweet_id=tweet_id, user_id=user.id)
            session.add(like_tweet)
            logger.info(f"Like created for user {user.id} on tweet {tweet_id}")
        else:  # лайк существует, удаляем его
            logger.info(f"Like already exists for user {user.id} on tweet {tweet_id}")
            session.delete(like_tweet)
            logger.info(f"Like deleted for user {user.id} on tweet {tweet_id}")

        session.commit()
        data = {"result": "true"}
        return jsonify(data), 200

    except Exception as e:
        session.rollback()
        logger.error(f"Error putting like on tweet: {e}")
        data = {"result": "false", "error_type": "server error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def write_new_tweet(api_key: str, tweet_data: str, tweet_media_ids: List[int] = []):
    try:
        user = session.query(User).filter_by(api_key=api_key).first()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        tweet = Tweet(user_id=user.id,
                      content=tweet_data,
                      attachments=tweet_media_ids)

        session.add(tweet)
        session.commit()

        logger.info(f"create tweet with media: {tweet_media_ids}")
        tweet_id = tweet.id
        logger.info(f"Created new tweet with id: {tweet_id}")

        data = {"result": "true", "tweet_id": tweet_id}
        return jsonify(data), 201

    except Exception as e:
        session.rollback()
        logger.error(f"Error writing tweet: {e}")
        data = {"result": "false", "error_type": "server error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def download_file(api_key: str, file: str):
    try:
        user = session.query(User).filter_by(api_key=api_key).first()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        filename = os.path.basename(file)
        media_url = f"/media/{filename}"
        logger.info(f"media_url: {media_url}")
        data = {"result": "true", "media_id": media_url}
        return jsonify(data), 201

    except Exception as e:
        logger.error(f"Error download file {file}: {e}")
        data = {"result": "false", "error_type": "error", "error_message": str(e)}
        return jsonify(data), 500


    except Exception as e:
        logger.error(f"Error download file {file}: {e}")
        data = {"result": "false", "error_type": "error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def delete_tweet_by_user(api_key: str, tweet_id: int):
    try:
        user = session.query(User).filter_by(api_key=api_key).one()
        if user is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        tweet = session.query(Tweet).filter_by(id=tweet_id).one()
        if tweet is None:
            logger.error(f"tweet with id {tweet_id} do not found")
            data = {"result": "false", "error_type": "invalid tweet_id",
                    "error_message": f"tweet with id {tweet_id} do not found"}
            return jsonify(data), 400

        if tweet.user_id != user.id:
            logger.error(f"user with api-key do not wrote tweet with id {tweet_id}")
            data = {"result": "false", "error_type": "error",
                    "error_message": f"user with api-key do not wrote tweet with id {tweet_id}"}
            return jsonify(data), 400

        session.delete(tweet)
        session.commit()

        data = {"result": "true"}
        return jsonify(data), 200

    except Exception as e:
        session.rollback()
        logger.error(f"Error writing tweet: {e}")
        data = {"result": "false", "error_type": "server error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def follow_user(api_key: str, user_id: int):
    try:
        logger.info("Start func follow_user")

        follower = session.query(User).filter_by(api_key=api_key).first()
        if follower is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        user = session.query(User).filter_by(id=user_id).first()
        if user is None:
            logger.error(f"User with id {user_id} do not found")
            data = {"result": "false", "error_type": "invalid user id",
                    "error_message": f"User with id {user_id} do not found"}
            return jsonify(data), 400

        if follower.id == user.id:
            logger.error("User do not following himself")
            data = {"result": "false", "error_type": "Error",
                    "error_message": "User do not following himself"}
            return jsonify(data), 400

        subscribe = session.query(SubscribedUser).filter_by(follower_user_id=follower.id,
                                                            subscribed_user_id=user.id).first()
        if subscribe is None:
            new_subscribe = SubscribedUser(follower_user_id=follower.id, subscribed_user_id=user.id)
            session.add(new_subscribe)
            session.commit()
            logger.info("Follower successfully subscribed on user")

        else:
            logger.info("Follower was subscribed on user early")

        data = {"result": "true"}
        return jsonify(data), 201


    except Exception as e:
        session.rollback()
        logger.error(f"Error during following: {e}")
        data = {"result": "false", "error_type": "error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def delete_following(api_key: str, user_id: int):
    try:
        logger.info("Start func follow_user")

        follower = session.query(User).filter_by(api_key=api_key).first()
        if follower is None:
            logger.error(f"user with api-key {api_key} do not found")
            data = {"result": "false", "error_type": "invalid api-key",
                    "error_message": "user with api-key do not found"}
            return jsonify(data), 400

        user = session.query(User).filter_by(id=user_id).first()
        if user is None:
            logger.error(f"User with id {user_id} do not found")
            data = {"result": "false", "error_type": "invalid user id",
                    "error_message": f"User with id {user_id} do not found"}
            return jsonify(data), 400

        if follower.id == user.id:
            logger.error("User do not following himself")
            data = {"result": "false", "error_type": "Error",
                    "error_message": "User do not following himself"}
            return jsonify(data), 400

        subscribe = session.query(SubscribedUser).filter_by(follower_user_id=follower.id,
                                                            subscribed_user_id=user.id).first()
        if subscribe is None:
            logger.info("Follower is not subscribed on user")


        else:
            session.delete(subscribe)
            session.commit()
            logger.info("Subscribe is delete")

        data = {"result": "true"}
        return jsonify(data), 201


    except Exception as e:
        session.rollback()
        logger.error(f"Error during following: {e}")
        data = {"result": "false", "error_type": "error", "error_message": str(e)}
        return jsonify(data), 500
    finally:
        session.close()


def get_info_user_profile(user_id):
    """Получение информации о пользователе по его id"""
    try:
        # Получаем пользователя
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            logger.error(f"User with id {user_id} is not found")
            return jsonify({
                "result": "false",
                "error_type": "invalid user id",
                "error_message": f"User with id {user_id} is not found"
            }), 400

        # Получаем пользователей, на которых подписан пользователь
        subscribed_users = session.query(SubscribedUser).filter_by(follower_user_id=user_id).all()
        subscribed_user_ids = [su.subscribed_user_id for su in subscribed_users]

        # Используем JOIN для эффективного запроса
        subscribed_users_data = session.query(User.id, User.name, User.surname).join(
            SubscribedUser, User.id == SubscribedUser.subscribed_user_id
        ).filter(SubscribedUser.follower_user_id == user_id).all()

        following_data = [{"id": sub[0], "name": f"{sub[1]} {sub[2]}"} for sub in subscribed_users_data]

        # Получаем пользователей, которые подписаны на пользователя
        following_users = session.query(SubscribedUser).filter_by(subscribed_user_id=user.id).all()
        following_user_ids = [fo.follower_user_id for fo in following_users]

        # Используем JOIN для эффективного запроса
        followers_data_query = session.query(User.id, User.name, User.surname).join(
            SubscribedUser, User.id == SubscribedUser.follower_user_id
        ).filter(SubscribedUser.subscribed_user_id == user.id).all()

        followers_data = [{"id": fo[0], "name": f"{fo[1]} {fo[2]}"} for fo in followers_data_query]

        tweets = session.query(Tweet).filter_by(user_id=user.id).all()

        data_tweets = []
        for tw in tweets:
            likes = session.query(LikeTweet).filter_by(tweet_id=tw.id).all()
            likes_list = [like.user_id for like in likes]
            tweet_info = {"id": tw.id, "content": tw.content, "attachments": tw.attachments, "likes": likes_list}
            data_tweets.append(tweet_info)

        result = {
            "user": {
                "id": user.id,
                "name": f"{user.name} {user.surname}",
                "following": following_data,
                "followers": followers_data,
                "tweets": data_tweets
            }
        }

        # Закрытие сессии лучше делать в блоке finally или использовать контекстный менеджер
        # session.close()

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error during get user profile: {e}")
        return jsonify({
            "result": "false",
            "error_type": "Invalid user profile",
            "error_message": str(e)
        }), 400
    finally:
        session.close()
