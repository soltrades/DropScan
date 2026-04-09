import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Supabase environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

class DB:
    _instance = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
            cls._instance = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return cls._instance

# Export a shorthand for getting the client
def get_db():
    return DB.get_client()
