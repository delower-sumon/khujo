import hashlib
from urllib.parse import urlparse

def compute_url_hash(url: str) -> str:
    """Compute a deterministic hash for a given URL for deduplication."""
    return hashlib.md5(url.strip().lower().encode("utf-8")).hexdigest()[:32]

def is_valid_article_url(url: str, target_domain: str) -> bool:
    """Filter out media files, login pages, and off-domain links."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    
    clean_netloc = parsed.netloc.replace("www.", "")
    target_clean = target_domain.replace("www.", "")
    if target_clean not in clean_netloc:
        return False

    path = parsed.path.lower()
    ignored_exts = (
        '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.css', '.js', 
        '.ico', '.svg', '.mp4', '.mp3', '.zip', '.tar', '.gz'
    )
    if path.endswith(ignored_exts):
        return False

    ignored_paths = (
        '/login', '/signup', '/register', '/cart', '/account', 
        '/search', '/tag/', '/category/', '/author/'
    )
    # Ignore utility paths if they are the primary path (short enough)
    if any(p in path for p in ignored_paths) and len(path) < 25:
        return False

    return True
