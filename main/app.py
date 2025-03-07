import os

from flask import Flask, render_template, send_from_directory, request, jsonify

from database.db_init import start_bd
from database.db_utils import get_tweets_by_user_api_key, get_user_by_api_key, put_or_delete_like_on_tweet, \
    write_new_tweet, \
    download_file, delete_tweet_by_user, follow_user, get_info_user_profile, delete_following
from utils import allowed_file
from werkzeug.utils import secure_filename
import uuid
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

HOST = '0.0.0.0'
PORT = 5000
UPLOAD_FOLDER = 'uploads'

root_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_ABSOLUTE = os.path.join(root_dir, UPLOAD_FOLDER)

template_folder = os.path.join(root_dir, "templates")
static_folder = os.path.join(root_dir, "static")

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder, static_url_path='')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_ABSOLUTE


@app.route('/css/<path:path>')
def send_css(path):
    css_folder = os.path.join(static_folder, 'css')
    file_path = os.path.join(css_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(css_folder, path)
    else:
        print(f"CSS файл {file_path} не найден")
        return "CSS файл не найден", 404


@app.route('/js/<path:path>')
def send_js(path):
    js_folder = os.path.join(static_folder, 'js')
    file_path = os.path.join(js_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(js_folder, path)
    else:
        print(f"JS файл {file_path} не найден")
        return "JS файл не найден", 404


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tweets", methods=["POST"])
def post_new_twit():
    api_key = request.headers.get('api-key')
    if not api_key:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": "api-key is required"}), 400
    try:
        data = request.get_json()

        if data is None:
            return jsonify({"result": "false", "error_type": "invalid json",
                            "error_message": "invalid json"}), 400

        tweet_data = data.get('tweet_data')
        if not tweet_data:
            return jsonify({"result": "false", "error_type": "invalid data",
                            "error_message": "tweet_data is required"}), 400

        tweet_media_ids = data.get('tweet_media_ids')
        logger.info(f"tweet_media_ids: {tweet_media_ids}, is it list: {isinstance(tweet_media_ids, list)}")

        if tweet_media_ids is not None and not isinstance(tweet_media_ids, list):
            return jsonify({"result": "false", "error_type": "invalid data",
                            "error_message": "tweet_media_ids must be an array"}), 400

        return write_new_tweet(api_key, tweet_data, tweet_media_ids)

    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": "e"}), 500


@app.route("/api/medias", methods=["POST"])
def post_download_medias():
    try:
        api_key = request.headers.get('api-key')
        if not api_key:
            logger.error(f"user with api-key {api_key} do not found")
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "api-key is required"}), 400

        if 'file' not in request.files:
            logger.error("file is not found")
            return jsonify({"result": "false", "error_type": "invalid data",
                            "error_message": "invalid data"}), 400

        file = request.files['file']
        logger.info(f"file: {file}")
        if file and allowed_file(file.filename):
            logger.info("file is allowed")

            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            logger.info(f"filename: {filename}, filepath: {filepath}")

            # Сохраняем файл
            file.save(filepath)
            logger.info("file was saved")

            return download_file(api_key, filepath)

    except Exception as e:
        logger.error(f"file is not saved, error: {e}")
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": str(e)}), 500


@app.route('/media/<path:path>')
def send_media(path):
    return send_from_directory(app.config['UPLOAD_FOLDER'], path)


@app.route("/api/tweets/<int:id>", methods=["DELETE"])
def delete_tweet(id: int):
    try:
        api_key = request.headers.get('api-key')
        if not api_key:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "api-key is required"}), 400

        if not id:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "tweet id is required"}), 400

        return delete_tweet_by_user(api_key, id)

    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": str(e)}), 500


@app.route("/api/users/me", methods=["GET"])
def info_user_profile():
    api_key = request.headers.get('api-key')
    if not api_key:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": "api-key is required"}), 400
    return get_user_by_api_key(api_key)


@app.route("/api/tweets", methods=["GET"])
def get_twits_user():
    api_key = request.headers.get('api-key')
    if not api_key:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": "api-key is required"}), 400

    return get_tweets_by_user_api_key(api_key)


@app.route("/api/tweets/<int:id>/likes", methods=["POST"])
def post_put_or_delete_like(id: int):
    api_key = request.headers.get('api-key')
    if not api_key:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": "api-key is required"}), 400
    return put_or_delete_like_on_tweet(api_key, id)


@app.route("/api/users/<int:id>/follow", methods=["POST"])
def post_follow_user(id: int):
    try:
        api_key = request.headers.get('api-key')
        if not api_key:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "api-key is required"}), 400

        if not id:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "user id is required"}), 400
        logger.info(f"api-key: {api_key}, user_id: {id}")
        return follow_user(api_key, id)

    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": f"error by following user: {str(e)}"}), 500


@app.route("/api/users/<int:id>/follow", methods=["DELETE"])
def delete_follow_user(id: int):
    try:
        api_key = request.headers.get('api-key')
        if not api_key:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "api-key is required"}), 400

        if not id:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "user id is required"}), 400
        logger.info(f"api-key: {api_key}, user_id: {id}")
        return delete_following(api_key, id)

    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": f"error by following user: {str(e)}"}), 500


@app.route("/api/users/<int:id>", methods=["GET"])
def get_user_profile(id: int):
    try:

        return get_info_user_profile(id)
    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": f"error by get user info: {str(e)}"}), 500


@app.route("/profile/<int:id>", methods=["GET"])
def get_user_info(id: int):
    try:
        if not id:
            return jsonify({"result": "false", "error_type": "Error",
                            "error_message": "user id is required"}), 400

        return get_info_user_profile(id)

    except Exception as e:
        return jsonify({"result": "false", "error_type": "Error",
                        "error_message": f"error by get user info: {str(e)}"}), 500


if __name__ == "__main__":
    start_bd()
    app.run(host=HOST, port=PORT)
