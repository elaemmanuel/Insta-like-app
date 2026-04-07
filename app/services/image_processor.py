# services/image_processor.py

from ..database import SessionLocal
from .. import crud
from app.services.ai_tagging import generate_tags

def process_image(filename: str) -> str:
    # Simulated AI logic (placeholder)
    return "car, outdoor, vehicle"

def process_and_save(filename: str, url: str):
    print("Processing image:", filename)

    tags = generate_tags(url)

    crud.create_image_cosmos(filename, tags, url)