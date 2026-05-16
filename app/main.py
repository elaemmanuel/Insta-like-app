

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body
from fastapi.middleware.cors import CORSMiddleware

import json
import os
import redis
import logging

from dotenv import load_dotenv

# Services
from app.services.blob_service import upload_file
from app.service_bus import send_message
from app.cosmos_db import container
from app.users_db import users_container


# =========================
# LOAD ENV
# =========================
load_dotenv()


# =========================
# LOGGING CONFIG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================
# FASTAPI INIT
# =========================
app = FastAPI()


# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# REDIS CONFIG
# =========================
redis_client = None

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=6380,
        password=os.getenv("REDIS_KEY"),
        ssl=True,
        decode_responses=True,
        socket_connect_timeout=7
    )

    redis_client.ping()

    logger.info("Redis connected successfully")

except Exception as e:
    logger.error(f"Redis disabled: {str(e)}")
    redis_client = None


CACHE_TTL = 60


# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    redis_status = "connected"

    try:
        if redis_client:
            redis_client.ping()
        else:
            redis_status = "disabled"

    except Exception:
        redis_status = "failed"

    return {
        "status": "healthy",
        "redis": redis_status
    }


# =========================
# UPLOAD IMAGE
# =========================
@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    caption: str = Form(""),
    title: str = Form(""),
    location: str = Form(""),
    people: str = Form(""),
    user_email: str = Form("")
):
    try:
        logger.info(f"Upload started by {user_email}")

        contents = await file.read()

        # CHECK USER
        user_query = f"SELECT * FROM c WHERE c.email = '{user_email}'"

        users = list(users_container.query_items(
            query=user_query,
            enable_cross_partition_query=True
        ))

        if not users:
            logger.warning(f"Upload blocked - user not found: {user_email}")
            raise HTTPException(status_code=404, detail="User not found")

        user = users[0]

        if user["role"] != "creator":
            logger.warning(f"Upload blocked - non creator: {user_email}")
            raise HTTPException(status_code=403, detail="Only creators can upload")

        # UPLOAD TO BLOB
        blob_url = upload_file(contents, file.filename)

        logger.info(f"Blob uploaded: {blob_url}")

        # DETECT TYPE
        file_type = (
            "video"
            if file.content_type.startswith("video")
            else "image"
        )

        people_list = [
            p.strip()
            for p in people.split(",")
            if p.strip()
        ]

        # SERVICE BUS MESSAGE
        message = {
            "filename": file.filename,
            "url": blob_url,
            "caption": caption,
            "title": title,
            "location": location,
            "people": people_list,
            "created_by": user_email,
            "type": file_type
        }

        send_message(json.dumps(message))

        logger.info(f"Service Bus message sent: {file.filename}")

        # CACHE INVALIDATION
        if redis_client:
            redis_client.delete("all_images")
            redis_client.delete(f"image:{file.filename}")

            logger.info("Redis cache invalidated")

        return {
            "message": "Uploaded successfully!",
            "url": blob_url
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Upload failed"
        )


# =========================
# GET SINGLE IMAGE
# =========================
@app.get("/image/{filename}")
def get_image(filename: str):
    try:
        cache_key = f"image:{filename}"

        # CACHE CHECK
        if redis_client:
            cached = redis_client.get(cache_key)

            if cached:
                logger.info(f"Redis cache hit: {filename}")
                return json.loads(cached)

        logger.info(f"Redis cache miss: {filename}")

        query = f"SELECT * FROM c WHERE c.id = '{filename}'"

        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if not items:
            logger.warning(f"Image not found: {filename}")

            raise HTTPException(
                status_code=404,
                detail="Image not found"
            )

        item = items[0]

        result = {
            "id": item["id"],
            "url": item["url"],
            "caption": item.get("caption", ""),
            "tags": item.get("tags", []),
            "comments": item.get("comments", []),
            "created_by": item.get("created_by", "unknown")
        }

        # STORE CACHE
        if redis_client:
            redis_client.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result)
            )

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Fetch single image failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Error fetching image"
        )


# =========================
# GET ALL IMAGES
# =========================
@app.get("/images")
def get_images():
    try:
        cache_key = "all_images"

        # CACHE CHECK
        if redis_client:
            cached = redis_client.get(cache_key)

            if cached:
                logger.info("Redis cache hit: all_images")
                return json.loads(cached)

        logger.info("Redis cache miss: all_images")

        images = list(container.read_all_items())

        result = []

        for item in images:
            result.append({
                "id": item["id"],
                "url": item["url"],
                "caption": item.get("caption", ""),
                "tags": item.get("tags", []),
                "comments": item.get("comments", []),
                "created_by": item.get("created_by", "unknown")
            })

        # STORE CACHE
        if redis_client:
            redis_client.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result)
            )

        logger.info(f"Fetched {len(result)} images")

        return result

    except Exception as e:
        logger.error(f"Fetch images failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch images"
        )


# =========================
# ADD COMMENT
# =========================
@app.post("/comment")
def add_comment(data: dict):

    try:
        filename = data["filename"]
        comment = data["comment"]
        user_email = data.get("user_email")

        logger.info(f"Comment attempt by {user_email}")

        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="User not provided"
            )

        # CHECK USER
        user_query = f"SELECT * FROM c WHERE c.email = '{user_email}'"

        users = list(users_container.query_items(
            query=user_query,
            enable_cross_partition_query=True
        ))

        if not users:
            logger.warning(f"Comment blocked - user not found: {user_email}")

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        user = users[0]

        # BLOCK CREATORS
        if user["role"] != "consumer":
            logger.warning(f"Comment blocked - creator attempted comment")

            raise HTTPException(
                status_code=403,
                detail="Only consumers can comment"
            )

        # GET IMAGE
        query = f"SELECT * FROM c WHERE c.id = '{filename}'"

        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if not items:
            raise HTTPException(
                status_code=404,
                detail="Image not found"
            )

        item = items[0]

        if "comments" not in item:
            item["comments"] = []

        item["comments"].append(comment)

        container.upsert_item(item)

        logger.info(f"Comment added to {filename}")

        # CACHE INVALIDATION
        if redis_client:
            redis_client.delete("all_images")
            redis_client.delete(f"image:{filename}")

            logger.info("Redis cache invalidated")

        return {
            "message": "Comment added"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Comment failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Failed to add comment"
        )


# =========================
# REGISTER
# =========================
@app.post("/register")
def register(data: dict = Body(...)):

    try:
        email = data["email"]

        logger.info(f"Registration attempt: {email}")

        query = f"SELECT * FROM c WHERE c.email = '{email}'"

        existing = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if existing:
            logger.warning(f"Registration blocked - user exists: {email}")

            raise HTTPException(
                status_code=400,
                detail="User already exists"
            )

        role = data.get("role", "consumer")

        if role not in ["creator", "consumer"]:
            role = "consumer"

        user = {
            "id": email,
            "email": email,
            "password": data["password"],
            "role": role
        }

        users_container.create_item(user)

        logger.info(f"User registered successfully: {email}")

        return {
            "message": "User registered"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Registration failed"
        )


# =========================
# LOGIN
# =========================
@app.post("/login")
def login(data: dict = Body(...)):

    try:
        email = data["email"].strip().lower()
        password = data["password"]

        logger.info(f"Login attempt: {email}")

        query = f"SELECT * FROM c WHERE c.email = '{email}'"

        users = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if not users:
            logger.warning(f"Login failed - user not found: {email}")

            raise HTTPException(
                status_code=401,
                detail="User not found"
            )

        user = users[0]

        if user["password"] != password:
            logger.warning(f"Login failed - invalid password: {email}")

            raise HTTPException(
                status_code=401,
                detail="Invalid password"
            )

        logger.info(f"Login success: {email}")

        return {
            "email": user["email"],
            "role": user["role"]
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Login failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )