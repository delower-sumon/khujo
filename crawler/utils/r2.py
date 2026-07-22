"""
Cloudflare R2 Media Vault client for KhujoBot v1.
Handles favicon uploads and retrieval.
"""

import os
import logging
from urllib.parse import urlparse
import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load env
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env = os.path.join(current_dir, "..", "..", "backend", ".env")
if os.path.exists(backend_env):
    load_dotenv(backend_env)
else:
    load_dotenv()

log = logging.getLogger(__name__)

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET = os.getenv("R2_BUCKET_NAME", "khujo")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"

def _get_s3_client():
    if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
        raise RuntimeError("R2 credentials missing. Check R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"}),
        region_name="auto",
    )

def upload_favicon(domain: str, favicon_bytes: bytes, content_type: str = "image/png") -> str:
    ext_map = {
        "image/png": "png",
        "image/x-icon": "ico",
        "image/vnd.microsoft.icon": "ico",
        "image/svg+xml": "svg",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    ext = ext_map.get(content_type, "ico")
    key = f"favicons/{domain}.{ext}"

    client = _get_s3_client()
    client.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=favicon_bytes,
        ContentType=content_type,
        CacheControl="public, max-age=604800",
    )
    return f"{R2_PUBLIC_URL}/{key}"

def fetch_and_upload_favicon(site_url: str) -> str | None:
    parsed = urlparse(site_url)
    domain = (parsed.netloc or parsed.path).replace("www.", "")

    # Try direct /favicon.ico
    favicon_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/favicon.ico"
    try:
        resp = requests.get(favicon_url, headers={"User-Agent": KHUJO_UA}, timeout=8, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 100:
            ct = resp.headers.get("Content-Type", "image/x-icon").split(";")[0].strip()
            return upload_favicon(domain, resp.content, ct)
    except Exception:
        pass

    # Try Google favicon service fallback
    google_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
    try:
        resp = requests.get(google_url, timeout=8, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 100:
            return upload_favicon(domain, resp.content, "image/png")
    except Exception:
        pass

    return None
