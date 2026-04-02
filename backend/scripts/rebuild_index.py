import os
import sys
from pathlib import Path

# Add backend to path so we can import our services
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.chunking import chunk_text_structurally
from app.services.vector_db import upsert_structural_chunks

def rebuild_index_from_local():
    """
    Scans the 'scraped_data' directory and re-indexes all found knowledge 
    back into the Pinecone Vector Database.
    """
    data_dir = "scraped_data"
    
    if not os.path.exists(data_dir):
        print(f"❌ Error: {data_dir} directory not found.")
        return

    files = [f for f in os.listdir(data_dir) if f.endswith("_Full_Knowledge.txt")]
    
    if not files:
        print("ℹ️ No knowledge files found to re-index.")
        return

    print(f"🔍 Found {len(files)} knowledge bases. Starting re-index...")

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)
        print(f"📄 Processing {file_name}...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    continue
                
                # Extract Source URL from the first line header
                # Header format: "UNIFIED KNOWLEDGE BASE FOR https://..."
                first_line = lines[0]
                source_url = first_line.replace("UNIFIED KNOWLEDGE BASE FOR ", "").strip()
                
                full_text = "".join(lines)
                
                # 1. Structural Chunking (This now includes our Breadcrumb & Diversity logic)
                print(f"   - Level 1: Generating structural chunks for {source_url}...")
                chunks = chunk_text_structurally(full_text, source_url)
                
                # 2. Upsert to Pinecone
                print(f"   - Level 2: Upserting {len(chunks)} chunks to Pinecone...")
                upsert_structural_chunks(chunks)
                
                print(f"✅ Successfully re-indexed {file_name}")

        except Exception as e:
            print(f"❌ Failed to process {file_name}: {str(e)}")

    print("\n🎉 Re-indexing complete! Your Vector Database is now fully restored.")

if __name__ == "__main__":
    rebuild_index_from_local()
