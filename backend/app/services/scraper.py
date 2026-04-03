from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse
from app.core.logging import app_logger as logger # Fix 1.3: Standardized Logging

async def scrape_single_page(browser_context, url: str) -> Dict[str, any]:
    """Helper for the parallel scraper to read one page."""
    page = await browser_context.new_page()
    
    # --- RESOURCE BLOCKER 🛡️ ---
    async def block_aggressively(route):
        block_types = {"image", "media", "font", "other"}
        block_domains = ["google-analytics", "googletagmanager", "facebook", "doubleclick", "hotjar", "hubspot"]
        url_lower = route.request.url.lower()
        if route.request.resource_type in block_types or any(d in url_lower for d in block_domains):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", block_aggressively)
    
    result = {
        "original_url": url.rstrip("/"),
        "final_url": url.rstrip("/"),
        "title": "Untitled Page",
        "text": "", 
        "links": []
    }
    
    try:
        try:
            await page.goto(url, wait_until="networkidle", timeout=35000)
        except Exception:
            try:
                # Fix 1.3: Log slow pages
                logger.warning("Scraper fallback engaged", extra={"url": url, "strategy": "domcontentloaded"})
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                logger.warning("Final scraper warning", extra={"url": url, "status": "unresponsive"})
            
        result["final_url"] = page.url.split("#")[0].rstrip("/")
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        result["title"] = soup.title.string.strip() if soup.title else "Untitled Page"
        
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for a in soup.find_all('a', href=True):
            full_link = urljoin(url, a['href'])
            if full_link.startswith(base_domain):
                result["links"].append({
                    "url": full_link.split("#")[0].rstrip("/"),
                    "text": a.get_text().strip().lower()
                })
        
        for junk in soup(["script", "style", "footer", "nav", "iframe"]):
            junk.extract()
        
        result["text"] = soup.get_text(separator='\n')
        return result
        
    except Exception:
        # Fix 5.2: Detailed traceback for scrape failures
        logger.error("Scrape failed critically", exc_info=True, extra={"url": url})
        return result
    finally:
        await page.close()

async def scrape_urls_parallel(urls: List[str], headless: bool = False) -> List[Dict[str, any]]:
    """Super-High Performance Parallel Scraper!"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720}
        )
        
        tasks = [scrape_single_page(context, url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        await browser.close()
        return results

async def scrape_url(url: str) -> Dict[str, any]:
    res = await scrape_urls_parallel([url], headless=False)
    return res[0]
