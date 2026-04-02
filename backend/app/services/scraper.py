from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse

async def scrape_single_page(browser_context, url: str) -> Dict[str, any]:
    """Helper for the parallel scraper to read one page."""
    page = await browser_context.new_page()
    result = {"url": url, "text": None, "links": []}
    
    try:
        # 30 second timeout per page
        await page.goto(url, wait_until="networkidle", timeout=30000)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # 1. Discover Links (Internal Only)
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for a in soup.find_all('a', href=True):
            full_link = urljoin(url, a['href'])
            if full_link.startswith(base_domain):
                result["links"].append({
                    "url": full_link.split("#")[0].rstrip("/"), # Cleaned URL
                    "text": a.get_text().strip().lower()
                })
        
        # 2. Extract Clean Text
        for junk in soup(["script", "style", "footer", "nav"]):
            junk.extract()
        
        result["text"] = soup.get_text(separator='\n')
        return result
        
    except Exception as e:
        print(f"Scraper error for {url}: {str(e)}")
        return result
    finally:
        await page.close()

async def scrape_urls_parallel(urls: List[str], headless: bool = False) -> List[Dict[str, any]]:
    """
    Super-High Performance Parallel Scraper!
    It opens one browser and many tabs (pages) simultaneously.
    """
    async with async_playwright() as p:
        # Launch one browser
        browser = await p.chromium.launch(headless=headless)
        # One context for all tabs
        context = await browser.new_context()
        
        # Batch create tasks for all URLs at the same time!
        tasks = [scrape_single_page(context, url) for url in urls]
        
        # MAGIC LINE: Run them all in parallel! 🚀
        results = await asyncio.gather(*tasks)
        
        await browser.close()
        return results

# Keep 'scrape_url' as a simplified wrapper if needed for single calls
async def scrape_url(url: str) -> Dict[str, any]:
    res = await scrape_urls_parallel([url], headless=False)
    return res[0]
