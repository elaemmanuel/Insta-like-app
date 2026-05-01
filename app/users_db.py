from azure.cosmos import CosmosClient
import os
from dotenv import load_dotenv

# ✅ Load env
load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")

# ✅ Connect
client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)

# ✅ USE SAME DB AS IMAGES
DATABASE_NAME = "image-db"

database = client.get_database_client(DATABASE_NAME)

# ✅ USERS CONTAINER
users_container = database.get_container_client("users")