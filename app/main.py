# from fastapi import FastAPI, UploadFile, File, HTTPException, Form
# from fastapi.middleware.cors import CORSMiddleware
# import json

# # Services
# from app.services.blob_service import upload_file
# from app.service_bus import send_message
# from app.cosmos_db import container

# app = FastAPI()

# # ✅ Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # ✅ UPLOAD IMAGE
# @app.post("/upload")
# async def upload_image(
#     file: UploadFile = File(...),
#     caption: str = Form("")
# ):
#     try:
#         contents = await file.read()

#         # Upload to Blob
#         blob_url = upload_file(contents, file.filename)
#         print("📦 BLOB URL:", blob_url)

#         # Send message to Service Bus
#         message = {
#             "filename": file.filename,
#             "url": blob_url,
#             "caption": caption
#         }

#         send_message(json.dumps(message))
#         print("📤 Message sent to queue")

#         return {
#             "message": "Uploaded successfully!",
#             "url": blob_url
#         }

#     except Exception as e:
#         print("❌ Upload failed:", str(e))
#         raise HTTPException(status_code=500, detail="Upload failed")


# # ✅ GET ALL IMAGES
# @app.get("/images")
# def get_images():
#     try:
#         images = container.read_all_items()

#         result = []
#         for item in images:
#             result.append({
#                 "id": item["id"],
#                 "url": item["url"],
#                 "caption": item.get("tags", "")
#             })

#         return result

#     except Exception as e:
#         print("❌ Fetch images failed:", str(e))
#         raise HTTPException(status_code=500, detail="Failed to fetch images")


# # ✅ GET SINGLE IMAGE
# @app.get("/image/{filename}")
# def get_image(filename: str):
#     try:
#         query = f"SELECT * FROM c WHERE c.id = '{filename}'"
#         items = list(container.query_items(
#             query=query,
#             enable_cross_partition_query=True
#         ))

#         if not items:
#             raise HTTPException(status_code=404, detail="Image not found")

#         return items[0]

#     except Exception as e:
#         print("❌ Fetch single image failed:", str(e))
#         raise HTTPException(status_code=500, detail="Error fetching image")






from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import redis

# Services
from app.services.blob_service import upload_file
from app.service_bus import send_message
from app.cosmos_db import container

app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ✅ REDIS CONFIG (SAFE)
# =========================
redis_client = None

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=6380,
        password=os.getenv("REDIS_KEY"),
        ssl=True,
        decode_responses=True,
        socket_connect_timeout=2
    )

    # Test connection
    redis_client.ping()
    print("✅ Redis connected")

except Exception as e:
    print("⚠️ Redis disabled:", str(e))
    redis_client = None

CACHE_TTL = 60


# =========================
# ✅ UPLOAD IMAGE
# =========================
@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    caption: str = Form("")
):
    try:
        contents = await file.read()

        # Upload to Blob
        blob_url = upload_file(contents, file.filename)
        print("📦 BLOB URL:", blob_url)

        # Send message to Service Bus
        message = {
            "filename": file.filename,
            "url": blob_url,
            "caption": caption
        }

        send_message(json.dumps(message))
        print("📤 Message sent to queue")

        # ❗ Invalidate cache after new upload
        if redis_client:
            redis_client.delete("all_images")

        return {
            "message": "Uploaded successfully!",
            "url": blob_url
        }

    except Exception as e:
        print("❌ Upload failed:", str(e))
        raise HTTPException(status_code=500, detail="Upload failed")


# =========================
# ✅ GET ALL IMAGES (WITH CACHE)
# =========================
@app.get("/images")
def get_images():
    try:
        cache_key = "all_images"

        # 1. Check Redis
        cached = redis_client.get(cache_key) if redis_client else None
        if cached:
            print("⚡ Cache hit (all images)")
            return json.loads(cached)

        print("🐢 Cache miss (all images)")

        # 2. Fetch from Cosmos DB
        images = container.read_all_items()

        result = []
        for item in images:
            result.append({
                "id": item["id"],
                "url": item["url"],
                "caption": item.get("caption", ""),
                "tags": item.get("tags", [])
            })

        # 3. Store in Redis
        if redis_client:
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result

    except Exception as e:
        print("❌ Fetch images failed:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch images")


# =========================
# ✅ GET SINGLE IMAGE (WITH CACHE)
# =========================
@app.get("/image/{filename}")
def get_image(filename: str):
    try:
        cache_key = f"image:{filename}"

        # 1. Check Redis
        cached = redis_client.get(cache_key) if redis_client else None
        if cached:
            print(f"⚡ Cache hit ({filename})")
            return json.loads(cached)

        print(f"🐢 Cache miss ({filename})")

        # 2. Query Cosmos DB
        query = f"SELECT * FROM c WHERE c.id = '{filename}'"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if not items:
            raise HTTPException(status_code=404, detail="Image not found")

        result = items[0]

        # 3. Store in Redis
        if redis_client:
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result

    except Exception as e:
        print("❌ Fetch single image failed:", str(e))
        raise HTTPException(status_code=500, detail="Error fetching image")