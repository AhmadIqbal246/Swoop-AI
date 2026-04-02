from app.core.celery_app import celery_app
from app.services.scraper import scrape_urls_parallel
from app.utils.text_cleanup import clean_raw_text
from app.utils.chunking import chunk_text_structurally
from app.services.vector_db import upsert_structural_chunks
from pinecone import Pinecone
from app.core.config import get_settings
import os
import asyncio
import time
from urllib.parse import urlparse

@celery_app.task(bind=True)
def process_url_task(self, url: str):
    """
    STRUCTURAL SITE MAPPER:
    Creates a High-Quality, Page-Aware Master Knowledge Base from an entire site.
    """
    logs = []
    def emit_log(msg: str, pages: list = None):
        # Only append distinct general phases to avoid explosion on large loops of the same string
        if not logs or logs[-1] != msg:
            logs.append(msg)
        self.update_state(state='PROGRESS', meta={
            'message': msg,
            'logs': logs,
            'processed_pages': pages or []
        })

    emit_log(f'Navigating to {url}...')
    
    # 1. DISCOVERY & IDENTITY-CORE INJECTION 🧠🔨
    # Regardless of where the user starts, we find the "Brain" of the site.
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}".rstrip("/")
    
    # Automatically seed the "Core Identity" pages for any domain
    to_scrape = {
        url,                    # The provided start URL
        base_url,               # The Root/Home Page
        f"{base_url}/about",    # Common About/Contact variants
        f"{base_url}/about-us",
        f"{base_url}/team",
        f"{base_url}/contact",
        f"{base_url}/contact-us"
    } 
    
    init_res = asyncio.run(scrape_urls_parallel([url], headless=False))
    init_data = init_res[0]
    
    # EXCLUSION LIST: Pages we KNOW are useless for an AI knowledge base
    excluded_patterns = [
        "privacy", "terms", "cookie", "legal", "disclaimer",
        "login", "signin", "signup", "register", "logout",
        "cart", "checkout", "account", "password", "reset",
        ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        "javascript:", "wp-admin", "wp-login",
        "?utm_", "?ref=", "?source="
    ]
    
    # Normalize the homepage for deduplication
    homepage_normalized = base_url.lower()
    
    for link in init_data.get("links", []):
        full_link = link["url"].rstrip("/")
        
        # Skip if it's the home page (already in set) or resolves to same anchor
        if full_link.lower() == homepage_normalized:
            continue
        
        # Skip excluded junk
        is_excluded = any(pattern in full_link.lower() for pattern in excluded_patterns)
        
        if not is_excluded and full_link not in to_scrape:
            to_scrape.add(full_link)

    # 2. PRIORITY SCORING ENGINE 🎯
    # We ensure high-value Identity pages (Team, About, Contact) are always in the TOP 15
    def get_priority_score(u):
        u_low = u.lower()
        if u_low == homepage_normalized: return 0
        identity_keywords = ["about", "team", "contact", "founder", "leadership"]
        if any(kw in u_low for kw in identity_keywords): return 1
        return 10 + len(u) # Deeper pages are secondary

    target_urls = sorted(list(to_scrape), key=get_priority_score)[:15]
    total_found = len(target_urls)
    
    # 2. THE SWOOP (Parallel Scrape)
    emit_log(f'Analyzing site architecture ({total_found} pages)...')
    all_results = asyncio.run(scrape_urls_parallel(target_urls, headless=False))
    
    # 3. KNOWLEDGE CONSOLIDATION & LIVE REPORTING
    master_text = ""
    export_dir = "scraped_data"
    os.makedirs(export_dir, exist_ok=True)
    
    processed_list = []
    
    for index, res in enumerate(all_results):
        final_url = res.get("final_url")
        original_url = res.get("original_url")
        title = res.get("title", "Unknown Page")
        raw_text = res.get("text")
        
        if not raw_text:
            continue
            
        cleaned = clean_raw_text(raw_text)
        processed_list.append(original_url)
        
        # LIVE PROGRESS UPDATE PER PAGE! 🚀
        emit_log(f'Gathering knowledge from {title}...', processed_list)
        
        # 1. Store under FINAL URL (The physical location)
        master_text += f"\n\n{'='*60}\n"
        master_text += f" SOURCE PAGE: {final_url} | TITLE: {title}\n"
        master_text += f"{'='*60}\n\n"
        master_text += cleaned + "\n"

        # 2. ALSO Store under ORIGINAL URL (If different, to ensure recognition)
        if original_url and original_url != final_url:
            master_text += f"\n\n{'='*60}\n"
            master_text += f" SOURCE PAGE: {original_url} | TITLE: {title}\n"
            master_text += f"{'='*60}\n\n"
            master_text += cleaned + "\n"

    # Export Unified Master Knowledge Base File
    parsed_domain = urlparse(url).netloc.replace(".", "_")
    master_file_name = f"{parsed_domain}_Full_Knowledge.txt"
    file_path = os.path.join(export_dir, master_file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"UNIFIED KNOWLEDGE BASE FOR {url}\n")
        f.write(f"Retrieved: {len(target_urls)} pages successfully mapped.\n")
        f.write(master_text)
        
    # 4. STRUCTURAL BATCH PROCESSING & VECTORIZATION
    emit_log('Processing site data...', processed_list)
    
    structural_chunks = chunk_text_structurally(master_text, source_url=url)
    upsert_structural_chunks(structural_chunks)

    # 5. PINECONE READINESS GATE ⏳
    # Wait for Pinecone eventual-consistency: poll until vector count increases.
    emit_log('Finalizing analysis...', processed_list)
    try:
        settings = get_settings()
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(settings.PINECONE_INDEX_NAME)
        # Get baseline vector count before upsert was called (it was just called, so poll for change)
        deadline = time.time() + 30  # wait up to 30 seconds
        while time.time() < deadline:
            stats = index.describe_index_stats()
            total_vectors = stats.get('total_vector_count', 0)
            if total_vectors > 0:
                break  # Index is live
            time.sleep(2)
    except Exception as e:
        # Non-fatal: log and continue
        print(f"Readiness check warning: {e}")

    return {
        "status": "COMPLETED",
        "message": "All set! I have finished reading the website and am ready to answer your questions.",
        "processed_pages": processed_list,
        "master_document": os.path.abspath(file_path)
    }
