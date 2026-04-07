from azure.cosmos import CosmosClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")

client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)

database = client.get_database_client("image-db")
container = database.get_container_client("images")