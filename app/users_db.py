from azure.cosmos import CosmosClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")

# ✅ CONNECT
client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)

# ✅ HARDCODE DB NAME (same as your working one)
DATABASE_NAME = "image-db"

print("✅ Connected to DB:", DATABASE_NAME)

database = client.get_database_client(DATABASE_NAME)

# ✅ USERS CONTAINER (create if not exists in Azure)
users_container = database.get_container_client("users")