import os
import sys
from pathlib import Path

# Add the project root to sys.path so we can import our app
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pinecone import Pinecone
from app.core.config import get_settings

def clear_pinecone_index():
    """
    🧹 CRITICAL SCRIPT: Deletes all vectors from the specified Pinecone index.
    Use this to 'Wipe the Brain' and start fresh!
    """
    settings = get_settings()
    
    print(f"🚀 Initializing Pinecone for: {settings.PINECONE_INDEX_NAME}")
    
    # Initialize connection
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    
    # Connect to the specific index
    index = pc.Index(settings.PINECONE_INDEX_NAME)
    
    # Confirm with user in terminal
    confirm = input(f"⚠️  WARNING: You are about to DELETE ALL DATA in '{settings.PINECONE_INDEX_NAME}'. Are you sure? (y/n): ")
    
    if confirm.lower() == 'y':
        print(f"🧹 Clearing index '{settings.PINECONE_INDEX_NAME}'...")
        # Delete all vectors in the index
        index.delete(delete_all=True)
        print("✅ Success! Your index is now completely empty.")
    else:
        print("❌ Operation cancelled. No data was deleted.")

if __name__ == "__main__":
    clear_pinecone_index()
