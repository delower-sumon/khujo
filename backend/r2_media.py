"""
r2_media.py — Cloudflare R2 Media Vault client
Handles favicon uploads/retrieval for Khujo.

Architecture rule: "Media never touches the VPS disk."
All media assets go to R2. The VPS stores only the public URL.
"""

import os
import io
import logging
from urllib.parse import urlparse

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

log = logging.getLogger(__name__)


# ── R2 Configuration ──────────────────────────────────────────
R2_ENDPOINT       = os.getenv("R2_ENDPOINT")
R2_BUCKET         = os.getenv("R2_BUCKET_NAME", "khujo")
R2_PUBLIC_URL     = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
R2_ACCESS_KEY     = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY     = os.getenv("R2_SECRET_ACCESS_KEY")

# User agent for fetching favicons from external sites
KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"


def _get_s3_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
        raise RuntimeError(
            "R2 credentials not configured. Set R2_ENDPOINT, R2_ACCESS_KEY_ID, "
            "and R2_SECRET_ACCESS_KEY in backend/.env"
        )
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 2, "mode": "standard"},
        ),
        region_name="auto",
    )


def verify_connection() -> dict:
    """
    Test that we can reach R2 and the bucket exists.
    Returns a status dict with success flag and details.
    """
    try:
        client = _get_s3_client()
        # HEAD bucket — lightweight check
        client.head_bucket(Bucket=R2_BUCKET)
        return {
            "success": True,
            "bucket": R2_BUCKET,
            "endpoint": R2_ENDPOINT,
            "public_url": R2_PUBLIC_URL,
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        return {"success": False, "error": f"ClientError {code}: {e}"}
    except NoCredentialsError:
        return {"success": False, "error": "No R2 credentials found in .env"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_favicon(domain: str, favicon_bytes: bytes, content_type: str = "image/png") -> str:
    """
    Upload a favicon to R2 under favicons/{domain}.ext
    Returns the public URL of the uploaded favicon.
    """
    # Determine file extension from content type
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
        CacheControl="public, max-age=604800",  # 7-day cache
    )

    public_url = f"{R2_PUBLIC_URL}/{key}"
    log.info("Uploaded favicon for %s -> %s (%d bytes)", domain, public_url, len(favicon_bytes))
    return public_url


def fetch_and_upload_favicon(site_url: str) -> str | None:
    """
    Given a website URL, try to fetch its favicon and upload to R2.
    Returns the public R2 URL, or None if no favicon could be found.

    Strategy (in order):
      1. Try /favicon.ico at the domain root
      2. Try Google's favicon service as fallback
    """
    parsed = urlparse(site_url)
    domain = parsed.netloc or parsed.path
    domain = domain.replace("www.", "")  # normalise

    # Strategy 1: Direct /favicon.ico
    favicon_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/favicon.ico"
    try:
        resp = requests.get(
            favicon_url,
            headers={"User-Agent": KHUJO_UA},
            timeout=10,
            allow_redirects=True,
        )
        if resp.status_code == 200 and len(resp.content) > 100:
            ct = resp.headers.get("Content-Type", "image/x-icon").split(";")[0].strip()
            return upload_favicon(domain, resp.content, ct)
    except requests.RequestException as e:
        log.debug("favicon.ico fetch failed for %s: %s", domain, e)

    # Strategy 2: Google favicon service (returns PNG)
    google_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
    try:
        resp = requests.get(google_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 100:
            return upload_favicon(domain, resp.content, "image/png")
    except requests.RequestException as e:
        log.debug("Google favicon fetch failed for %s: %s", domain, e)

    return None


def get_favicon_url(domain: str) -> str:
    """
    Construct the expected public URL for a domain's favicon.
    Does NOT check if it exists — used for fast lookups.
    """
    # Default to .ico, the most common format we store
    return f"{R2_PUBLIC_URL}/favicons/{domain}.ico"


# ── CLI: Run directly to verify connection ─────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Cloudflare R2 Connection Test")
    print("=" * 50)

    result = verify_connection()
    if result["success"]:
        print(f"  Bucket:     {result['bucket']}")
        print(f"  Endpoint:   {result['endpoint']}")
        print(f"  Public URL: {result['public_url']}")
        print("\n  R2 connection verified successfully!")
    else:
        print(f"  FAILED: {result['error']}")
