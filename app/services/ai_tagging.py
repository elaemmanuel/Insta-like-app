import os
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

VISION_ENDPOINT = os.getenv("VISION_ENDPOINT")
VISION_KEY = os.getenv("VISION_KEY")

client = ImageAnalysisClient(
    endpoint=VISION_ENDPOINT,
    credential=AzureKeyCredential(VISION_KEY)
)

def generate_tags(image_url: str):
    result = client.analyze_from_url(
        image_url=image_url,
        visual_features=[VisualFeatures.TAGS]
    )

    tags = [tag.name for tag in result.tags.list]

    return tags