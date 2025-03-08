import asyncio
import os
import uuid
import logging
from typing import List

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request, Header
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from aiofiles import open as aio_open
from fastapi.staticfiles import StaticFiles

from database.db_init import start_bd, get_db
from database import db_utils
from utils import allowed_file
from werkzeug.utils import secure_filename

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# Конфигурация приложения
HOST = '0.0.0.0'
PORT = 8000
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'

root_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_ABSOLUTE = os.path.join(root_dir, UPLOAD_FOLDER)
TEMPLATES_FOLDER_ABSOLUTE = os.path.join(root_dir, "templates")
STATIC_FOLDER_ABSOLUTE = os.path.join(root_dir, STATIC_FOLDER)

app = FastAPI()

# Настройка статических файлов
app.mount("/static", StaticFiles(directory=STATIC_FOLDER_ABSOLUTE, html=True), name="static")

# Маршруты для перенаправления
@app.get("/js/{path:path}")
async def redirect_js(path: str):
    return RedirectResponse(url=f"/static/js/{path}", status_code=301)

@app.get("/css/{path:path}")
async def redirect_css(path: str):
    return RedirectResponse(url=f"/static/css/{path}", status_code=301)


# Модели запросов
class TweetCreate(BaseModel):
    tweet_data: str
    tweet_media_ids: List[int] = []


# Хелперы
def get_upload_file_path(filename: str) -> str:
    return os.path.join(UPLOAD_FOLDER_ABSOLUTE, filename)


# Роуты
@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        template_path = os.path.join(TEMPLATES_FOLDER_ABSOLUTE, "index.html")
        async with aio_open(template_path, "r") as f:
            content = await f.read()
        return content
    except Exception as e:
        logger.error(f"Error reading index.html: {e}")
        raise HTTPException(status_code=500, detail="Failed to read index.html")


@app.post("/api/tweets")
async def create_tweet(
        tweet_data: TweetCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    logger.debug("create_tweet function was called!")

    try:
        logger.info(
            f"Start func write_new_tweet with tweet data: {tweet_data.tweet_data} tweet media {tweet_data.tweet_media_ids}")
        return await db_utils.write_new_tweet(db, api_key, tweet_data.tweet_data, tweet_data.tweet_media_ids)
    except Exception as e:
        logger.exception("Error creating tweet")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/medias")
async def upload_media(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    logger.debug("upload_media function was called!")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = get_upload_file_path(unique_filename)

        logger.debug(f"filename: {filename}, filepath: {filepath}")

        # Асинхронное сохранение файла
        contents = await file.read()
        async with aio_open(filepath, "wb") as f:
            await f.write(contents)
        logger.debug("file saved")

        return await db_utils.download_file(db, api_key, filepath)
    except Exception as e:
        logger.exception("Error saving media file")
        raise HTTPException(status_code=500, detail=str(e))


async def get_media(id: int, db: AsyncSession = Depends(get_db)):
    try:
        logger.debug(f"get_media function was called with id: {id}")
        media_path = await db_utils.get_file_path(db, id)
        logger.debug(f"Media path retrieved: {media_path}")

        if not os.path.exists(media_path):
            logger.error(f"File not found at path: {media_path}")
            raise HTTPException(status_code=404, detail="File not found")

        async def iterfile():
            try:
                async with aio_open(media_path, "rb") as f:
                    while chunk := await f.read(1024 * 1024):
                        yield chunk
            except FileNotFoundError:
                logger.error(f"File disappeared: {media_path}")
                raise HTTPException(status_code=404, detail="File disappeared")
            except PermissionError:
                logger.error(f"Permission denied for file: {media_path}")
                raise HTTPException(status_code=403, detail="Permission denied")
            except Exception as e:
                logger.exception(f"Error reading file: {media_path}")
                raise HTTPException(status_code=500, detail="Internal server error")

        return StreamingResponse(iterfile(), media_type="image/jpeg")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("Error in get_media")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/{id}")
async def get_media_endpoint(id: int, db: AsyncSession = Depends(get_db)):
    try:
        id = int(id)  # Преобразуем id в целое число
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    try:
        return await get_media(id, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tweets/{id}")
async def delete_tweet(
        id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    try:
        return await db_utils.delete_tweet_by_user(db, api_key, id)
    except Exception as e:
        logger.exception("Error deleting tweet")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/me")
async def get_current_user(
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    logger.debug("get_current_user function was called!")
    try:
        return await db_utils.get_info_user(db, api_key=api_key)
    except Exception as e:
        logger.exception("Error getting user info")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tweets")
async def get_user_tweets(
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    logger.debug("get_user_tweets function was called!")

    try:
        return await db_utils.get_tweets_by_user_api_key(db, api_key)
    except Exception as e:
        logger.exception("Error getting tweets")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tweets/{id}/likes")
async def toggle_like(
        id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    try:
        return await db_utils.put_or_delete_like_on_tweet(db, api_key, id)
    except Exception as e:
        logger.exception("Error toggling like")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users/{id}/follow")
async def follow_user(
        id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    try:
        return await db_utils.follow_user(db, api_key, id)
    except Exception as e:
        logger.exception("Error following user")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/users/{id}/follow")
async def unfollow_user(
        id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Header(..., alias='api-key')
):
    try:
        return await db_utils.delete_following(db, api_key, id)
    except Exception as e:
        logger.exception("Error unfollowing user")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/{id}")
@app.get("/profile/{id}")
async def get_user_profile(
        id: int,
        db: AsyncSession = Depends(get_db)
):
    try:
        return await db_utils.get_info_user(db, user_id=id)
    except Exception as e:
        logger.exception("Error getting user profile")
        raise HTTPException(status_code=500, detail=str(e))


async def main():
    await start_bd(UPLOAD_FOLDER_ABSOLUTE)
    uvicorn_config = uvicorn.Config(app, host=HOST, port=PORT)
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    import uvicorn

    asyncio.run(main())
