

from app.services.ai_tagging import generate_tags
from app import crud

def process_and_save(
    filename: str,
    url: str,
    caption: str = "",
    title: str = "",
    location: str = "",
    people=None,
    created_by: str = "",
    file_type: str = "image"
):
    try:
        print(f"🔍 Generating tags for: {filename}")

        # ✅ AI tags (always list)
        ai_tags = generate_tags(url)
        print("AI Tags:", ai_tags)

        # ✅ FIX: keep tags as LIST
        combined_tags = ai_tags.copy()

        if caption:
            combined_tags.append(caption)

        print("Final Tags:", combined_tags)

        # ✅ SAVE EVERYTHING
        crud.create_image_cosmos(
            filename=filename,
            tags=combined_tags,
            url=url,
            caption=caption,
            title=title,
            location=location,
            people=people,
            created_by=created_by,
            file_type=file_type
        )

        print(f"💾 Saved to Cosmos DB: {filename}")

    except Exception as e:
        print("❌ PROCESSING FAILED:", str(e))
        raise e