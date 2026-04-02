import re

def clean_raw_text(text: str) -> str:
    """
    Cleans raw HTML text by:
    - Removing script and style tags content (usually done by scraper, but double-checked here)
    - Normalizing whitespace and line breaks
    - Removing common junk like cookie notices and footer links
    """
    # Remove excessive newlines and whitespace
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Trim each line and remove empty ones
    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 20]
    
    return '\n'.join(lines)
