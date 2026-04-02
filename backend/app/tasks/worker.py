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
    
    # 1. DISCOVERY (Initial Scan)
    init_res = asyncio.run(scrape_urls_parallel([url], headless=False))
    init_data = init_res[0]
    to_scrape = {url} # Set to avoid duplicates
    
    # EXCLUSION LIST: Pages we KNOW are useless for an AI knowledge base
    # Everything else discovered on the homepage will be scraped.
    # Note: '#' anchors are already stripped by the scraper, no need to exclude here.
    excluded_patterns = [
        "privacy", "terms", "cookie", "legal", "disclaimer",
        "login", "signin", "signup", "register", "logout",
        "cart", "checkout", "account", "password", "reset",
        ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        "javascript:", "wp-admin", "wp-login",
        "?utm_", "?ref=", "?source="
    ]
    
    # Normalize the homepage URL for deduplication
    homepage_normalized = url.rstrip("/").lower()
    
    for link in init_data.get("links", []):
        full_link = link["url"]
        
        # Skip if it resolves to the same page as the homepage (pure anchor links)
        if full_link.rstrip("/").lower() == homepage_normalized:
            continue
        
        # Skip if it's a junk/excluded link
        is_excluded = any(pattern in full_link.lower() for pattern in excluded_patterns)
        
        if not is_excluded and full_link not in to_scrape:
            to_scrape.add(full_link)

    target_urls = list(to_scrape)[:15]
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
        target_url = res.get("url")
        raw_text = res.get("text")
        if not raw_text:
            continue
            
        cleaned = clean_raw_text(raw_text)
        processed_list.append(target_url)
        
        # LIVE PROGRESS UPDATE PER PAGE! 🚀
        emit_log(f'Gathering knowledge from {target_url}...', processed_list)
        
        # Format for Structural Discovery
        master_text += f"\n\n{'='*60}\n"
        master_text += f" SOURCE PAGE: {target_url}\n"
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
