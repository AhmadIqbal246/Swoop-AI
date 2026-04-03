from app.core.celery_app import celery_app
from app.services.scraper import scrape_urls_parallel
from app.utils.text_cleanup import clean_raw_text
from app.utils.chunking import chunk_text_structurally
from app.services.vector_db import upsert_structural_chunks
from pinecone import Pinecone
from app.core.config import get_settings
from app.core.logging import app_logger as logger # Fix 1.5: Standardized Logging
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
    task_id = self.request.id
    start_time = time.perf_counter()
    logger.info("URL processing task started", extra={"task_id": task_id, "url": url}) # Fix 1.5 lifecycle

    logs = []

    def is_cancelled():
        try:
            val = celery_app.backend.client.get(f"cancelled:{task_id}")
            return val == b"true"
        except Exception:
            return False

    def emit_log(msg: str, pages: list = None):
        if is_cancelled(): return
        if not logs or logs[-1] != msg:
            logs.append(msg)
        self.update_state(state='PROGRESS', meta={
            'message': msg,
            'processed_pages': pages or []
        })

    if is_cancelled(): 
        logger.warning("Task cancelled before starting", extra={"task_id": task_id})
        return {"status": "REVOKED", "message": "Task cancelled before starting."}

    emit_log(f'Navigating to {url}...')
    
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}".rstrip("/")
    
    to_scrape = {
        url, base_url, f"{base_url}/about", f"{base_url}/about-us", f"{base_url}/team", f"{base_url}/contact", f"{base_url}/contact-us"
    } 
    
    try:
        init_res = asyncio.run(scrape_urls_parallel([url], headless=False))
        if is_cancelled(): return {"status": "REVOKED", "message": "Swoop aborted during discovery."}
        
        init_data = init_res[0]
        excluded_patterns = ["privacy", "terms", "cookie", "legal", "disclaimer", "login", "signin", "signup", "register", "logout", "cart", "checkout", "account", ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", "wp-admin", "wp-login"]
        
        homepage_normalized = base_url.lower()
        for link in init_data.get("links", []):
            full_link = link["url"].rstrip("/")
            if full_link.lower() == homepage_normalized: continue
            is_excluded = any(pattern in full_link.lower() for pattern in excluded_patterns)
            if not is_excluded and full_link not in to_scrape:
                to_scrape.add(full_link)

        def get_priority_score(u):
            u_low = u.lower()
            if u_low == homepage_normalized: return 0
            identity_keywords = ["about", "team", "contact", "founder", "leadership"]
            if any(kw in u_low for kw in identity_keywords): return 1
            return 10 + len(u)

        target_urls = sorted(list(to_scrape), key=get_priority_score)[:15]
        total_found = len(target_urls)
        
        emit_log(f'Analyzing site architecture ({total_found} pages)...')
        all_results = asyncio.run(scrape_urls_parallel(target_urls, headless=False))
        
        if is_cancelled(): return {"status": "REVOKED", "message": "Swoop aborted during parallel mapping."}
        
        master_text = ""
        export_dir = "scraped_data"
        os.makedirs(export_dir, exist_ok=True)
        processed_list = []
        
        for index, res in enumerate(all_results):
            if is_cancelled(): return {"status": "REVOKED", "message": "Swoop aborted during data consolidation."}
            
            final_url = res.get("final_url")
            original_url = res.get("original_url")
            title = res.get("title", "Unknown Page")
            raw_text = res.get("text")
            
            if not raw_text: continue
            processed_list.append(original_url)
            emit_log(f'Gathering knowledge from {title}...', processed_list)
            
            cleaned = clean_raw_text(raw_text)
            master_text += f"\n\n{'='*60}\n SOURCE PAGE: {final_url} | TITLE: {title}\n{'='*60}\n\n{cleaned}\n"

        from app.utils.domain_tools import normalize_to_domain
        p_domain_norm = normalize_to_domain(url)
        parsed_domain_file = p_domain_norm.replace(".", "_") if p_domain_norm else urlparse(url).netloc.replace(".", "_")
        file_path = os.path.join(export_dir, f"{parsed_domain_file}_Full_Knowledge.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(master_text)
            
        if is_cancelled(): return {"status": "REVOKED", "message": "Swoop aborted before vectorization."}
        emit_log('Processing site data...', processed_list)
        
        structural_chunks = chunk_text_structurally(master_text, source_url=url)
        upsert_structural_chunks(structural_chunks, source_url=url)

        # Readiness gate
        emit_log('Finalizing analysis...', processed_list)
        try:
            pc = Pinecone(api_key=get_settings().PINECONE_API_KEY)
            index = pc.Index(get_settings().PINECONE_INDEX_NAME)
            deadline = time.time() + 30
            while time.time() < deadline:
                if is_cancelled(): break
                stats = index.describe_index_stats()
                if stats.get('total_vector_count', 0) > 0: break
                time.sleep(2)
        except Exception as e:
            logger.warning("Index readiness check failed", exc_info=True)

        # Registry update
        try:
            import json
            from app.utils.domain_tools import normalize_to_domain
            registry_path = os.path.join(export_dir, "entities_registry.json")
            registry = {}
            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as rf: registry = json.load(rf)
            
            p_domain = normalize_to_domain(url)
            if p_domain:
                registry[p_domain] = { 
                    "url": url, 
                    "status": "INDEXED", 
                    "pages_counted": len(processed_list), 
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S") 
                }
                with open(registry_path, "w", encoding="utf-8") as wf: json.dump(registry, wf, indent=4)
        except Exception:
            logger.warning("Registry update failed", exc_info=True)

        duration = time.perf_counter() - start_time
        logger.info("URL processing completed", extra={"task_id": task_id, "duration": duration, "pages": len(processed_list)}) # Fix 1.5 lifecycle
        
        return {
            "status": "COMPLETED",
            "message": "All set!",
            "processed_pages": processed_list,
            "master_document": os.path.abspath(file_path)
        }
    except Exception:
        logger.error("Critical worker failure", exc_info=True, extra={"task_id": task_id, "url": url})
        return {"status": "FAILED", "message": "Critical failure during scraping."}
