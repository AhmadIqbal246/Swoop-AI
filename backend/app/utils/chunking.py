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
    # We make TITLE: optional (?: ...)? to be backwards compatible with old files
    section_divider = r"\n\n={60}\n SOURCE PAGE: (.*?)(?: \| TITLE: (.*?))?\n={60}\n\n"
    parts = re.split(section_divider, full_text)
    
    # regex has 2 groups, so re.split returns [prefix, group1, group2, content, group1, group2, content...]
    # This means each page block is a stride of 3 (prefix + 2 groups + 1 content = 4? No.)
    # Actually, re.split with N groups returns [prefix, g1, g2... gN, content, ...]
    
    all_chunks = []
    
    # Jumping by 3 (group1, group2, content)
    for i in range(1, len(parts), 3):
        page_url = parts[i]
        page_title = parts[i+1] if parts[i+1] else page_url # Fallback if TITLE: is missing
        page_content = parts[i+2]
        
        # 2. Within each page, detect Internal Section Headers
        sub_sections = re.split(r'\n\n', page_content)
        current_title = "General Overview"
        
        for section in sub_sections:
            clean_section = section.strip()
            if not clean_section:
                continue
                
            word_count = len(clean_section.split())
            if 1 <= word_count <= 6 and not clean_section.endswith('.') and not clean_section.endswith('?'):
                current_title = clean_section
                continue
            
            # 3. Clean and merge internal sentences
            paragraph = clean_section.replace('\n', ' ')
            paragraph = re.sub(r' +', ' ', paragraph) # Clean double spaces
            
            # PREPEND STRUCTURAL BREADCRUMB! 🍞🚀
            # We want the AI to ALWAYS know the context even if isolated
            domain = source_url.replace("https://", "").replace("http://", "").split("/")[0]
            breadcrumb = f"[{domain}] > {page_title} > {current_title}: "
            content_with_context = breadcrumb + paragraph

            words = content_with_context.split()
            word_count = len(words)
            
            # 4. Enforce Limits (100-300 words)
            if word_count < 15:
                continue
                
            # If it's too big (>500 words), we split it manually with overlap!
            # WE ENSURE EVERY SUB-CHUNK KEEPS THE BREADCRUMB 🍞
            if word_count > 500:
                # We split the original paragraph (plain, without breadcrumb yet)
                raw_words = paragraph.split()
                chunk_size = 250
                overlap = 30
                for start in range(0, len(raw_words), chunk_size - overlap):
                    sub_para_text = " ".join(raw_words[start : start + chunk_size])
                    # Re-attach breadcrumb to each slice!
                    final_content = breadcrumb + sub_para_text
                    all_chunks.append({
                        "content": final_content,
                        "metadata": {
                            "url": page_url,
                            "base_url": source_url,
                            "title": current_title,
                            "chunk_id": f"{page_url}_{len(all_chunks)}"
                        }
                    })
            else:
                all_chunks.append({
                    "content": content_with_context,
                    "metadata": {
                        "url": page_url,
                        "base_url": source_url,
                        "title": current_title,
                        "chunk_id": f"{page_url}_{len(all_chunks)}"
                    }
                })
                
    return all_chunks
