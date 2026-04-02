import os
import json
import re
from urllib.parse import urlparse

def sync_registry():
    scraped_dir = "scraped_data"
    registry_path = os.path.join(scraped_dir, "entities_registry.json")
    
    # Load existing or create new
    registry = {}
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except: pass

    # Scan for Knowledge files
    # Pattern: [domain]_Full_Knowledge.txt
    files = os.listdir(scraped_dir)
    added_count = 0
    
    for filename in files:
        if filename.endswith("_Full_Knowledge.txt"):
            domain_slug = filename.replace("_Full_Knowledge.txt", "")
            # Convert slug back to a domain-like string (guesswork but accurate enough for the list)
            domain = domain_slug.replace("_", ".")
            
            if domain not in registry:
                registry[domain] = {
                    "url": f"https://{domain}",
                    "status": "INDEXED",
                    "pages_counted": "History",
                    "last_updated": "Pre-Registry"
                }
                added_count += 1
                
    # Force add known companies from user's logs if they aren't there
    known_companies = ["www.devsinc.com", "www.falconxoft.com", "codefinity.com", "ezitech.org"]
    for kc in known_companies:
        if kc not in registry:
            registry[kc] = {
                 "url": f"https://{kc}",
                 "status": "INDEXED",
                 "pages_counted": "History",
                 "last_updated": "Pre-Registry"
            }
            added_count += 1

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=4)
    
    print(f"SUCCESS: Synced {added_count} historical entities into the registry.")

if __name__ == "__main__":
    sync_registry()
