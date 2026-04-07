from pydantic import BaseModel

class ImageResponse(BaseModel):
    id: int
    filename: str
    tags: str | None

    class Config:
        from_attributes = True