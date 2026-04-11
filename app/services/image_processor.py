from app.services.ai_tagging import generate_tags
from app import crud


def process_and_save(filename: str, url: str, caption: str = ""):
    try:
        print(f"🔍 Generating tags for: {filename}")

        # ✅ AI tags
        ai_tags = generate_tags(url)
        print("AI Tags:", ai_tags)

        # ✅ Combine caption + AI tags
        combined_tags = f"{caption}, {ai_tags}" if caption else ai_tags

        print("Final Tags:", combined_tags)

        # ✅ Save to Cosmos DB
        crud.create_image_cosmos(filename, combined_tags, url)

        print(f"💾 Saved to Cosmos DB: {filename}")

    except Exception as e:
        print("❌ PROCESSING FAILED:", str(e))
        raise e