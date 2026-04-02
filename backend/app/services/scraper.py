from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse

async def scrape_single_page(browser_context, url: str) -> Dict[str, any]:
    """Helper for the parallel scraper to read one page."""
    page = await browser_context.new_page()
    
    # --- RESOURCE BLOCKER 🛡️ ---
    # We block heavy media (videos/images) and trackers to hit 'networkidle' in 1/10th the time.
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
        # Increase timeout to 60s for slow enterprise sites
        # Use a real browser user agent to avoid bot-detection
        # --- RESILIENT MULTI-STAGE LOADING 🛰️🏎️ ---
        # We try for Perfection (networkidle), but fall back to Speed (domcontentloaded)
        # This solves the "Sydney Video" problem for sites like Devsinc.
        try:
            await page.goto(url, wait_until="networkidle", timeout=35000)
        except Exception:
            try:
                print(f"Speed Fallback: Re-syncing {url} with base load...")
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                # Final Emergency: If even domcontentloaded fails, it's a dead site
                print(f"Final warning for {url}: Site is exceptionally slow or unresponsive.")
            
        # Capture the actual destination after redirects
        result["final_url"] = page.url.split("#")[0].rstrip("/")
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # 1. Capture Page Metadata
        result["title"] = soup.title.string.strip() if soup.title else "Untitled Page"
        
        # 2. Discover Links (Internal Only)
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for a in soup.find_all('a', href=True):
            full_link = urljoin(url, a['href'])
            if full_link.startswith(base_domain):
                result["links"].append({
                    "url": full_link.split("#")[0].rstrip("/"), # Cleaned URL
                    "text": a.get_text().strip().lower()
                })
        
        # 3. Extract Clean Text
        # We strip junk but keep the payload
        for junk in soup(["script", "style", "footer", "nav", "iframe"]):
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
        # Set a realistic User Agent to avoid bot-blocking
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720}
        )
        
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
