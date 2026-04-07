from sqlalchemy.orm import Session
from . import models

def create_image(db: Session, filename: str, tags: str):
    db_image = models.Image(filename=filename, tags=tags)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image

def get_images(db: Session):
    return db.query(models.Image).all()


from .cosmos_db import container
import uuid

def create_image_cosmos(filename: str, tags: list, url: str):
# Check if already exists
    existing = get_image_cosmos(filename)

    if existing:
        print("Already processed, skipping:", filename)
        return existing
    item = {
        "id": str(uuid.uuid4()),
        "filename": filename,
        "url": url,
        "tags": tags,
        "status": "processed"
    }

    print("Saving to Cosmos DB:", item)

    container.create_item(body=item)

    return item

def get_image_cosmos(filename: str):
    query = "SELECT * FROM c WHERE c.filename=@filename"
    parameters = [{"name": "@filename", "value": filename}]

    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))

    return items[0] if items else None