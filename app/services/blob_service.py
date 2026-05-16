import os
import uuid
import urllib.parse
from azure.storage.blob import BlobServiceClient, ContentSettings

# Load environment variables
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER")

# Init client
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(BLOB_CONTAINER)

# Ensure container exists
try:
    container_client.create_container(public_access="blob")
except:
    pass


def get_content_type(filename: str):
    ext = filename.split(".")[-1].lower()

    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"
    elif ext == "png":
        return "image/png"
    elif ext == "webp":
        return "image/webp"
    else:
        return "application/octet-stream"


def upload_file(file_bytes, filename):
    # ✅ 1. Generate unique + safe filename
    unique_name = f"{uuid.uuid4()}-{filename}"
    safe_filename = urllib.parse.quote(unique_name)

    print("Uploading filename:", filename)
    print("Safe filename:", safe_filename)
    print("Container:", BLOB_CONTAINER)

    # ✅ 2. Detect correct content type
    content_type = get_content_type(filename)
    print("Content-Type:", content_type)

    # ✅ 3. Get blob client
    blob_client = container_client.get_blob_client(safe_filename)

    # ✅ 4. DELETE if exists (fix Azure metadata bug)
    try:
        if blob_client.exists():
            blob_client.delete_blob()
            print("Deleted existing blob")
    except Exception as e:
        print("Delete check error:", e)

    # ✅ 5. Upload with correct headers
    blob_client.upload_blob(
        file_bytes,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type)
    )

    # ✅ 6. Generate URL
    blob_url = f"https://media.elariapp.co.uk/{safe_filename}"

    print("FINAL BLOB URL:", blob_url)

    return blob_url