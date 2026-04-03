import re
from urllib.parse import urlparse
from typing import Optional

def normalize_to_domain(text: str) -> Optional[str]:
    """
    STREET-SMART DOMAIN EXTRACTOR 🛰️
    Turns 'https://www.falconxoft.com/about' or 'downsize.com.au' into 'falconxoft.com'
    """
    if not text:
        return None

    # Step 1: Clean basic whitespace and lower-case it
    clean_text = text.strip().lower()

    # Step 2: Handle "Dirty" domains that don't have http (e.g. downsize.com.au)
    # If it contains a dot and doesn't start with http, we "Pre-fix" it for urlparse.
    if "." in clean_text and not clean_text.startswith("http"):
        # Very crude check to avoid catching "Dec 3. 2024" type strings
        if not re.search(r"\s", clean_text): # If no spaces, likely a lone URL
             clean_text = f"https://{clean_text}"

    # Step 3: Parse
    try:
        parsed = urlparse(clean_text)
        netloc = parsed.netloc
        
        if not netloc:
            # Re-try for cases where urlparse missed it
            return None
            
        # Step 4: Remove 'www.' prefix if present
        domain = netloc.replace("www.", "")
        
        # Step 5: Final Sanity Check (must contain at least one dot)
        if "." in domain:
            return domain
    except Exception:
        return None
        
    return None

def extract_urls_from_query(query: str) -> list[str]:
    """
    Finds anything that looks like a URL or domain in a natural language string.
    """
    # Pattern for URLs or Domain-looking words
    url_pattern = r'(https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-z]{2,})'
    found = re.findall(url_pattern, query)
    
    # Process each finding to get a clean list of root domains
    normalized_domains = []
    for item in found:
        domain = normalize_to_domain(item)
        if domain:
            normalized_domains.append(domain)
            
    return list(set(normalized_domains)) # Unique only
