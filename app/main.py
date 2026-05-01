
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import redis

# Services
from app.services.blob_service import upload_file
from app.service_bus import send_message
from app.cosmos_db import container
from app.users_db import users_container

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
        images = list(container.read_all_items())

        result = []

        for item in images:
            result.append({
                "id": item["id"],
                "url": item["url"],

                # ✅ KEEP BOTH (VERY IMPORTANT)
                "caption": item.get("caption", ""),
                "tags": item.get("tags", []),

                # ✅ COMMENTS (for UI)
                "comments": item.get("comments", [])
            })

        # 3. Store in Redis
        if redis_client:
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result

    except Exception as e:
        print("❌ Fetch images failed:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch images")

# POST COMMENT
@app.post("/comment")
def add_comment(data: dict):
    filename = data["filename"]
    comment = data["comment"]

    # ✅ FIX: use id, not filename
    query = f"SELECT * FROM c WHERE c.id = '{filename}'"

    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    if not items:
        raise HTTPException(status_code=404, detail="Image not found")

    item = items[0]

    if "comments" not in item:
        item["comments"] = []

    item["comments"].append(comment)

    container.upsert_item(item)

    # ✅ CLEAR CACHE so UI updates
    if redis_client:
        redis_client.delete("all_images")

    return {"message": "Comment added"}


@app.post("/register")
def register(data: dict = Body(...)):
    try:
        email = data["email"].strip().lower()
        password = data["password"]

        print("📥 Register attempt:", email)

        # ✅ Check if user exists
        query = f"SELECT * FROM c WHERE c.email = '{email}'"

        existing = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        # ✅ Create user
        user = {
            "id": email,
            "email": email,
            "password": password,
            "role": data.get("role", "consumer")
        }

        print("💾 Saving user:", user)

        users_container.create_item(user)

        print("✅ User saved to Cosmos")

        return {"message": "User registered"}

    except Exception as e:
        print("❌ REGISTER ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login")
def login(data: dict = Body(...)):
    try:
        email = data["email"].strip().lower()
        password = data["password"]

        print("🔐 Login attempt:", email)

        query = f"SELECT * FROM c WHERE c.email = '{email}'"

        users = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        print("👀 Found users:", users)

        if not users:
            raise HTTPException(status_code=401, detail="User not found")

        user = users[0]

        if user["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid password")

        print("✅ Login success")

        return {
            "email": user["email"],
            "role": user["role"]
        }

    except Exception as e:
        print("❌ LOGIN ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))