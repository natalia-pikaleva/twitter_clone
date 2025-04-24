import logging
import os
import uuid
from pathlib import Path
from typing import List

from aiofiles import open as aio_open
from main.database.db_utils import (
    download_file,
    write_new_tweet,
    get_file_path,
    delete_tweet_by_user,
    delete_following,
    follow_user,
    put_or_delete_like_on_tweet,
    get_info_user,
    get_tweets_by_user_api_key,
)

from main.database.db_init import get_db, start_bd
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
    FileResponse
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from main.utils import allowed_file
from werkzeug.utils import secure_filename

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - " "%(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# Конфигурация приложения
HOST = "0.0.0.0"
PORT = 8000
UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"

root_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_ABSOLUTE = os.path.join(root_dir, UPLOAD_FOLDER)
# TEMPLATES_FOLDER_ABSOLUTE = os.path.join(root_dir, "templates")
TEMPLATES_FOLDER_ABSOLUTE = "/app/templates"
# STATIC_FOLDER_ABSOLUTE = os.path.join(root_dir, STATIC_FOLDER)
STATIC_FOLDER_ABSOLUTE = "/app/static"

app = FastAPI()

app.mount("/static", StaticFiles(directory=STATIC_FOLDER_ABSOLUTE), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@app.middleware("http")
async def static_file_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/js/"):
        new_path = path.replace("/js/", "/static/js/", 1)
        try:
            return FileResponse(os.path.join(STATIC_FOLDER_ABSOLUTE, "js", new_path.split("/static/js/", 1)[1]))
        except FileNotFoundError:
            return await call_next(request)  # Если файл не найден, передаем дальше
    elif path.startswith("/css/"):
        new_path = path.replace("/css/", "/static/css/", 1)
        try:
            return FileResponse(os.path.join(STATIC_FOLDER_ABSOLUTE, "css", new_path.split("/static/css/", 1)[1]))
        except FileNotFoundError:
            return await call_next(request)  # Если файл не найден, передаем дальше

    response = await call_next(request)
    return response


# Модели запросов
class TweetCreate(BaseModel):
    tweet_data: str
    tweet_media_ids: List[int] = []


# Хелперы
def get_upload_file_path(filename: str) -> str:
    return os.path.join(UPLOAD_FOLDER_ABSOLUTE, filename)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,  # Возвращаем весь объект `detail` как тело ответа
    )


# Роуты
@app.get("/", response_class=HTMLResponse)
async def read_root() -> str:
    try:
        logger.debug("read_root function was called!")
        template_path = os.path.join(TEMPLATES_FOLDER_ABSOLUTE, "index.html")
        async with aio_open(template_path, "r") as f:
            content = await f.read()
        return content
    except Exception as e:
        logger.error(f"Error reading index.html: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "result": "false",
                "error_type": "Error",
                "error_message": "Failed to read index.html",
            },
        )


@app.post("/api/tweets")
async def create_tweet(
        tweet_data: TweetCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Create tweet
    """
    logger.debug("create_tweet function was called!")

    logger.info(
        f"Start func write_new_tweet with tweet data: "
        f"{tweet_data.tweet_data} "
        f"tweet media {tweet_data.tweet_media_ids}"
    )
    return await write_new_tweet(
        db, api_key, tweet_data.tweet_data, tweet_data.tweet_media_ids
    )


@app.post("/api/medias")
async def upload_media(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Upload media
    """
    logger.debug("upload_media function was called!")

    if not file:
        raise HTTPException(
            status_code=400,
            detail={
                "result": "false",
                "error_type": "FileError",
                "error_message": "No file uploaded",
            },
        )

    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail={
                "result": "false",
                "error_type": "FileError",
                "error_message": "Invalid file type",
            },
        )

    filename = secure_filename(file.filename)
    if not filename:
        filename = ""
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = get_upload_file_path(unique_filename)

    logger.debug(f"filename: {filename}, filepath: {filepath}")

    # Асинхронное сохранение файла
    contents = await file.read()
    async with aio_open(filepath, "wb") as f:
        await f.write(contents)
    logger.debug("file saved")

    return await download_file(db, api_key, filepath)


async def get_media(id: int, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Get media
    """
    logger.debug(f"get_media function was called with id: {id}")
    media_path = await get_file_path(db, id)
    logger.debug(f"Media path retrieved: {media_path}")

    async def iterfile():
        try:
            async with aio_open(media_path, "rb") as f:
                while chunk := await f.read(1024 * 1024):
                    yield chunk
        except FileNotFoundError:
            logger.error(f"File disappeared: {media_path}")
            raise HTTPException(
                status_code=404,
                detail={
                    "result": "false",
                    "error_type": "FileNotFoundError",
                    "error_message": "File disappeared",
                },
            )
        except PermissionError:
            logger.error(f"Permission denied for file: {media_path}")
            raise HTTPException(
                status_code=403,
                detail={
                    "result": "false",
                    "error_type": "PermissionError",
                    "error_message": "Permission denied",
                },
            )
        except Exception as e:
            logger.exception(f"Error reading file: {media_path}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "result": "false",
                    "error_type": "Error",
                    "error_message": f"Internal server error: {str(e)}",
                },
            )

    return StreamingResponse(iterfile(), media_type="image/jpeg")


@app.get("/{id}")
async def get_media_endpoint(
        id: int, db: AsyncSession = Depends(get_db)
) -> JSONResponse:  # noqa: B008
    """
    Get media file
    """
    try:
        logger.debug("get_media_endpoint function was called!")
        id = int(id)  # Преобразуем id в целое число
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "result": "false",
                "error_type": "ValueError",
                "error_message": "Invalid ID format",
            },
        )

    return await get_media(id, db)


@app.delete("/api/tweets/{id}")
async def delete_tweet(
        id: int,
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Delete tweet
    """
    return await delete_tweet_by_user(db, api_key, id)


@app.get("/api/users/me")
async def get_current_user(
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Get info about current user
    """
    logger.debug("get_current_user function was called!")
    return await get_info_user(db, api_key=api_key)


@app.get("/api/tweets")
async def get_user_tweets(
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Get tweets
    """
    logger.debug("get_user_tweets function was called!")

    return await get_tweets_by_user_api_key(db, api_key)


@app.post("/api/tweets/{id}/likes")
async def put_and_delete_like(
        id: int,
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Create and delete like on tweet
    """
    return await put_or_delete_like_on_tweet(db, api_key, id)


@app.post("/api/users/{id}/follow")
async def post_follow_user(
        id: int,
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Follow current user
    """
    return await follow_user(db, api_key, id)


@app.delete("/api/users/{id}/follow")
async def unfollow_user(
        id: int,
        db: AsyncSession = Depends(get_db),  # noqa: B008
        api_key: str = Header(..., alias="api-key"),
) -> JSONResponse:
    """
    Unfollow current user
    """
    return await delete_following(db, api_key, id)


@app.get("/api/users/{id}")
@app.get("/profile/{id}")
async def get_user_profile(
        id: int, db: AsyncSession = Depends(get_db)
) -> JSONResponse:  # noqa: B008
    """
    Get user profile
    """
    return await get_info_user(db, user_id=id)


@app.on_event("startup")
async def startup_event():
    """
    Start BD
    """
    try:
        logger.debug("Start sratup_event function")
        await start_bd(UPLOAD_FOLDER_ABSOLUTE)
    except Exception as e:
        logger.error(f"Error during function startup_event: {e}")
