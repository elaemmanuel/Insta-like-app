import os
import uuid

from azure.storage.blob import (
    BlobServiceClient,
    ContentSettings
)

BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER")

blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

container_client = blob_service_client.get_container_client(BLOB_CONTAINER)

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

    elif ext == "mp4":
        return "video/mp4"

    return "application/octet-stream"


def upload_file(file_bytes, filename):

    # REMOVE SPACES
    clean_filename = filename.replace(" ", "-")

    # UNIQUE NAME
    unique_name = f"{uuid.uuid4()}-{clean_filename}"

    content_type = get_content_type(filename)

    blob_client = container_client.get_blob_client(unique_name)

    blob_client.upload_blob(
        file_bytes,
        overwrite=True,
        content_settings=ContentSettings(
            content_type=content_type
        )
    )

    # CDN URL
    blob_url = (
        f"https://media.elariapp.co.uk/{unique_name}"
    )

    return blob_url