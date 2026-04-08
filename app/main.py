from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException
from .services.blob_service import upload_file
from sqlalchemy.orm import Session
from .services.image_processor import process_and_save
from .database import engine, SessionLocal, Base
from . import crud
from .services.image_processor import process_image
from fastapi.staticfiles import StaticFiles
import shutil, os
from .service_bus import send_message
from .cosmos_db import container
import json
import redis


redis_client = redis.Redis(
    host="redis",   # service name from docker-compose
    port=6379,
    decode_responses=True
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.post("/upload")
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    contents = await file.read()

    # Upload to Azure Blob
    blob_url = upload_file(contents, file.filename)
    print("BLOB URL:", blob_url)  # debugging

    # Send message to worker with URL
    message = {"filename": file.filename, "url": blob_url}
    send_message(json.dumps(message))

    return {"message": "Uploaded successfully!", "url": blob_url}


@app.get("/images")
def list_images():
    return crud.get_images_cosmos()



@app.get("/image/{filename}")
def get_image(filename: str):

    # 🔥 1. CHECK REDIS FIRST
    cached = redis_client.get(filename)

    if cached:
        print("Cache HIT")
        return json.loads(cached)

    print("Cache MISS")

    # 2. FETCH FROM COSMOS DB
    item = crud.get_image_cosmos(filename)

    if not item:
        raise HTTPException(status_code=404, detail="Image not found")

    # 3. STORE IN REDIS
    redis_client.setex(filename, 3600, json.dumps(item))

    return item