from typing import List, Dict
import re

def chunk_text_structurally(full_text: str, source_url: str) -> List[Dict[str, any]]:
    """
    IMPLEMENTS: High-Quality Structural/Document-Aware Chunking.
    
    1. Splits text by headers/sections.
    2. Merges related lines into clean paragraphs.
    3. Respects logical limits (100-300 words).
    4. Attaches RICH metadata (URL, Section Title, ID).
    """
    # 1. Split into Sections (Search for headers/double newlines)
    # We look for sections separated by the specific header format we used in our master file
    section_divider = r"\n\n={60}\n SOURCE PAGE: (.*?)\n={60}\n\n"
    parts = re.split(section_divider, full_text)
    
    # parts[0] is the unified knowledge intro
    # parts[1] is URL1
    # parts[2] is Page1 Text
    # and so on...
    
    all_chunks = []
    
    # We skip the very first header info in the text (parts[0])
    for i in range(1, len(parts), 2):
        page_url = parts[i]
        page_content = parts[i+1]
        
        # 2. Within each page, detect Internal Section Headers
        # Sub-sections (like "Why Choose Us", "FAQ", etc.) usually have 1-4 words.
        sub_sections = re.split(r'\n\n', page_content)
        
        current_title = "General Overview"
        
        for section in sub_sections:
            clean_section = section.strip()
            if not clean_section:
                continue
                
            # Detect if this block is a "Header" (short, usually start of a section)
            # and doesn't end with a period.
            word_count = len(clean_section.split())
            if 1 <= word_count <= 6 and not clean_section.endswith('.') and not clean_section.endswith('?'):
                current_title = clean_section
                continue
            
            # 3. Clean and merge internal sentences
            # Remove single newlines to create coherent paragraphs
            paragraph = clean_section.replace('\n', ' ')
            paragraph = re.sub(r' +', ' ', paragraph) # Clean double spaces
            
            words = paragraph.split()
            word_count = len(words)
            
            # 4. Enforce Limits (100-300 words)
            # If the paragraph is too small, we ignore tiny fragments (like "Read More")
            if word_count < 15:
                continue
                
            # If it's too big (>500 words), we split it manually with overlap!
            if word_count > 500:
                chunk_size = 300
                overlap = 50
                for start in range(0, word_count, chunk_size - overlap):
                    sub_para = " ".join(words[start : start + chunk_size])
                    all_chunks.append({
                        "content": sub_para,
                        "metadata": {
                            "url": page_url,
                            "base_url": source_url,
                            "title": current_title,
                            "chunk_id": f"{page_url}_{len(all_chunks)}"
                        }
                    })
            else:
                all_chunks.append({
                    "content": paragraph,
                    "metadata": {
                        "url": page_url,
                        "base_url": source_url,
                        "title": current_title,
                        "chunk_id": f"{page_url}_{len(all_chunks)}"
                    }
                })
                
    return all_chunks
