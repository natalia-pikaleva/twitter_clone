import logging
from typing import List

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from main.models import (LikeTweet, Media, SubscribedUser,
                         Tweet, User)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - "
                              "%(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


async def check_api_key_user(db: AsyncSession, api_key: str) -> User:
    """Проверка существования пользователя с указанным api-key"""
    result = await db.execute(select(User).filter_by(api_key=api_key))
    user = result.scalars().first()

    if not user:
        logger.error(f"User with api-key {api_key} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "result": "false",
                "error_type": "ValueError",
                "error_message": "User with provided api_key not found",
            },
        )
    return user


async def get_tweets_by_user_api_key(db: AsyncSession,
                                     api_key: str) -> JSONResponse:
    """
    Асинхронный поиск твитов пользователей, на которых подписан
    пользователь по его api-key
    """
    try:
        user = await check_api_key_user(db, api_key)

        # Получаем пользователей, на которых подписан наш пользователь
        result = await db.execute(
            select(SubscribedUser).filter_by(follower_user_id=user.id)
        )
        subscribed_users = result.scalars().all()

        # Получаем id пользователей, на которых подписан наш пользователь
        subscribed_user_ids = [su.subscribed_user_id
                               for su in subscribed_users]

        # Если пользователь не подписан ни на кого, то возвращаем пустой список
        if not subscribed_user_ids:
            subscribed_user_ids = []

        # Получаем все твиты из базы данных
        result = await db.execute(
            select(Tweet).options(
                selectinload(Tweet.user), selectinload(Tweet.liked_by)
            )
        )

        tweets = result.scalars().all()

        # Подсчитываем количество лайков для каждого твита и формируем ответ
        data_tweets = []
        for tweet in tweets:
            author = tweet.user
            likes_count = len(tweet.liked_by)  # Количество лайков
            likes_ids = [like.user_id for like in tweet.liked_by]

            # Проверяем, подписан ли пользователь на автора твита
            is_subscribed = author.id in subscribed_user_ids

            data_tweet = {
                "id": tweet.id,
                "content": tweet.content,
                "attachments": tweet.attachments,
                "author": {"id": author.id,
                           "name": f"{author.name} {author.surname}"},
                "likes": likes_ids,
                "likes_count": likes_count,
                "is_subscribed": is_subscribed,
            }
            data_tweets.append(data_tweet)

        # Сортируем твиты по количеству лайков в порядке убывания
        # среди подписок
        data_tweets.sort(key=lambda x: (not x["is_subscribed"],
                                        -x["likes_count"]))

        content = {"result": "true", "tweets": data_tweets}
        return JSONResponse(content=content, status_code=status.HTTP_200_OK)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during get tweets of user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "InternalServerError",
                "error_message": f"Error during get tweets of user: {e}",
            },
        )


async def put_or_delete_like_on_tweet(db: AsyncSession,
                                      api_key: str,
                                      tweet_id: int) -> JSONResponse:
    """Пользователь с данным api-key ставит лайк на твит с tweet_id"""
    try:
        user = await check_api_key_user(db, api_key)

        result = await db.execute(select(Tweet).filter_by(id=tweet_id))
        tweet = result.scalars().first()
        if not tweet:
            logger.error(f"tweet with id {tweet_id} do not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "ValueError",
                    "error_message": "Tweet with provided id not found",
                },
            )

        # Пытаемся получить существующий лайк
        result = await db.execute(
            select(LikeTweet).filter_by(user_id=user.id, tweet_id=tweet_id)
        )
        like_tweet = result.scalars().first()
        if like_tweet is None:  # лайк не существует, устанавливаем его
            logger.info(f"Like do not exist for "
                        f"user {user.id} on tweet {tweet_id}")
            like_tweet = LikeTweet(tweet_id=tweet_id, user_id=user.id)
            db.add(like_tweet)
            logger.info(f"Like created for user {user.id} on tweet {tweet_id}")
        else:  # лайк существует, удаляем его
            logger.info(f"Like already exists for user "
                        f"{user.id} on tweet {tweet_id}")
            await db.delete(like_tweet)
            logger.info(f"Like deleted for user {user.id} on tweet {tweet_id}")

        await db.commit()
        return JSONResponse(content={"result": "true"},
                            status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error putting like on tweet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "Error",
                "error_message": f"Error putting like on tweet: {e}",
            },
        )


async def write_new_tweet(
    db: AsyncSession,
        api_key: str,
        tweet_data: str,
        tweet_media_ids: List[int] = []
) -> JSONResponse:
    try:
        user = await check_api_key_user(db, api_key)

        tweet = Tweet(user_id=user.id,
                      content=tweet_data,
                      attachments=tweet_media_ids)

        db.add(tweet)
        await db.flush()
        await db.refresh(tweet)

        logger.info(f"create tweet with media: {tweet_media_ids}")
        tweet_id = tweet.id
        logger.info(f"Created new tweet with id: {tweet_id}")

        result = {"result": "true", "tweet_id": tweet_id}
        return JSONResponse(content=result,
                            status_code=status.HTTP_201_CREATED)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating new tweet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "Error",
                "error_message": f"Error creating new tweet: {e}",
            },
        )


async def download_file(db: AsyncSession,
                        api_key: str,
                        filepath: str) -> JSONResponse:
    try:
        logger.debug("download_file function was called")
        user = await check_api_key_user(db, api_key)

        media = Media(path=filepath)

        db.add(media)
        await db.commit()
        await db.refresh(media)

        logger.info("media saved in bd")
        media_id = media.id

        result = {"result": "true", "media_id": media_id}
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "FileError",
                "error_message": f"Error during file upload: {e}",
            },
        )


async def get_file_path(db: AsyncSession,
                        file_id: int) -> str:
    """
    Возвращает путь к файлу по его ID.
    """
    try:
        logger.debug(f"get_file_path function was called "
                     f"with file_id: {file_id}")
        result = await db.execute(
            select(Media.path).where(Media.id == file_id)
        )  # Получаем только путь
        file_path = (
            result.scalar_one_or_none()
        )  # Получаем один скалярный результат или None

        if file_path is None:
            logger.error(f"File with id {file_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "FileError",
                    "error_message": f"File with id {file_id} not found",
                },
            )

        logger.debug(f"File path: {file_path}")
        return file_path
    except HTTPException as e:
        raise e  # Пробрасываем HTTPException дальше
    except Exception as e:
        logger.error(f"Error getting file path: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "FileServerError",
                "error_message": "Could not retrieve file path",
            },
        )


async def delete_tweet_by_user(db: AsyncSession,
                               api_key: str,
                               tweet_id: int) -> JSONResponse:
    try:
        user = await check_api_key_user(db, api_key)

        result = await db.execute(select(Tweet).filter_by(id=tweet_id,
                                                          user_id=user.id))
        tweet = result.scalars().first()
        if not tweet:
            logger.error(f"tweet with id {tweet_id} "
                         f"do not found for user {user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "Error",
                    "error_message": "Tweet not found or "
                                     "does not belong to the user",
                },
            )

        await db.delete(tweet)
        await db.commit()

        return JSONResponse(content={"result": "true"},
                            status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting tweet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "InternalServerError",
                "error_message": f"Error deleting tweet: {e}",
            },
        )


async def follow_user(db: AsyncSession,
                      api_key: str,
                      user_id_to_follow: int) -> JSONResponse:
    try:
        # Получаем пользователя, который подписывается, по его API-ключу
        follower_user = await check_api_key_user(db, api_key)

        # Получаем пользователя, на которого подписываются, по его ID
        result = await db.execute(select(User).filter_by(id=user_id_to_follow))
        subscribed_user = result.scalars().first()
        if not subscribed_user:
            logger.error(f"Пользователь с id {user_id_to_follow} не найден")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "Error",
                    "error_message": "User with id not found",
                },
            )

        # Проверяем, не подписан ли уже пользователь
        result = await db.execute(
            select(SubscribedUser).filter_by(
                follower_user_id=follower_user.id,
                subscribed_user_id=subscribed_user.id
            )
        )
        existing_subscription = result.scalars().first()
        if existing_subscription:
            logger.info(
                f"Пользователь {follower_user.id} уже подписан "
                f"на пользователя {subscribed_user.id}"
            )

            return JSONResponse(
                content={"result": "true"}, status_code=status.HTTP_200_OK
            )

        # Создаем новую подписку
        new_subscription = SubscribedUser(
            follower_user_id=follower_user.id,
            subscribed_user_id=subscribed_user.id
        )
        db.add(new_subscription)
        await db.commit()

        logger.info(
            f"Пользователь {follower_user.id} успешно "
            f"подписался на пользователя {subscribed_user.id}"
        )

        return JSONResponse(
            content={"result": "true"}, status_code=status.HTTP_201_CREATED
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при подписке на пользователя: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "InternalServerError",
                "error_message": f"Ошибка при подписке на пользователя: {e}",
            },
        )


async def delete_following(db: AsyncSession,
                           api_key: str,
                           user_id_to_unfollow: int) -> JSONResponse:
    try:
        # Получаем пользователя, который отписывается, по его API-ключу
        follower_user = await check_api_key_user(db, api_key)

        if not follower_user:
            logger.error(f"Пользователь с api-key {api_key} не найден")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "ValueError",
                    "error_message": "User with provided api_key not found",
                },
            )

        # Получаем пользователя, от которого отписываются, по его ID
        result = await db.execute(select(User).
                                  filter_by(id=user_id_to_unfollow))
        subscribed_user = result.scalars().first()
        if not subscribed_user:
            logger.error(f"Пользователь с id {user_id_to_unfollow} не найден")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "Error",
                    "error_message": "User with id not found",
                },
            )

        # Пытаемся найти подписку между этими пользователями
        result = await db.execute(
            select(SubscribedUser).filter_by(
                follower_user_id=follower_user.id,
                subscribed_user_id=subscribed_user.id
            )
        )
        existing_subscription = result.scalars().first()
        if not existing_subscription:
            logger.info(
                f"Пользователь {follower_user.id} не подписан "
                f"на пользователя {subscribed_user.id}"
            )
            return JSONResponse(
                content={"result": "true"}, status_code=status.HTTP_200_OK
            )

        # Удаляем подписку
        await db.delete(existing_subscription)
        await db.commit()

        logger.info(
            f"Пользователь {follower_user.id} успешно "
            f"отписался от пользователя {subscribed_user.id}"
        )

        return JSONResponse(content={"result": "true"},
                            status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при отписке от пользователя: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "InternalServerError",
                "error_message": f"Ошибка при отписке от пользователя: {e}",
            },
        )


async def get_info_user(db: AsyncSession,
                        user_id: int = 0,
                        api_key: str = "") -> JSONResponse:
    try:
        if user_id == 0 and api_key == "":
            logger.error(
                "Некорректные данные для поиска пользователя, "
                "id и api-key не переданы"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "ValueError",
                    "error_message": "Invalid input, "
                                     "missing api-key and user_id",
                },
            )
        # Получаем пользователя по его ID или api-key
        if user_id != 0:
            result = await db.execute(select(User).filter_by(id=user_id))
        else:
            result = await db.execute(select(User).filter_by(api_key=api_key))

        user = result.scalars().first()
        if not user:
            logger.error(f"Пользователь с id {user_id} и "
                         f"api-key {api_key} не найден")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "result": "false",
                    "error_type": "ValueError",
                    "error_message": "User with api_key or id not found",
                },
            )

        # Получаем список подписчиков пользователя
        result = await db.execute(
            select(SubscribedUser).filter_by(subscribed_user_id=user.id)
        )
        followers = result.scalars().all()
        followers_ids = [follower.follower_user_id for follower in followers]

        # Получаем список подписок пользователя
        result = await db.execute(
            select(SubscribedUser).filter_by(follower_user_id=user.id)
        )
        following = result.scalars().all()
        following_ids = [follow.subscribed_user_id for follow in following]

        # Формируем информацию о пользователе
        user_info = {
            "id": user.id,
            "name": f"{user.name} {user.surname}",
            "followers": followers_ids,
            "following": following_ids,
        }

        logger.info(
            f"Информация о пользователе с id {user_id} и "
            f"api-key {api_key} успешно получена"
        )

        return JSONResponse(
            content={"result": "true", "user": user_info},
            status_code=status.HTTP_200_OK,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "result": "false",
                "error_type": "InternalServerError",
                "error_message": f"Error during get info user: {str(e)}",
            },
        )
