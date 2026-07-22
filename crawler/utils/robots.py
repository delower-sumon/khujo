"""
KhujoBot v1 — Robust Robots.txt Parser Utility (utils/robots.py)
Fixes stdlib urllib.robotparser bugs with Allow: rules and user-agent matching.
"""

import logging
import re
from urllib.parse import urlparse
import requests

log = logging.getLogger(__name__)

CACHE = {}

def is_url_allowed(url: str, user_agent: str = "KhujoBot/1.0") -> bool:
    """
    Parse site's robots.txt and check if the given URL is allowed for user_agent.
    Correctly respects Allow: and Disallow: directives.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    robots_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/robots.txt"

    if domain not in CACHE:
        CACHE[domain] = fetch_and_parse_robots(robots_url, user_agent)

    rules = CACHE[domain]
    path = parsed.path or "/"

    # Check Disallow rules first
    for disallow_pattern in rules["disallow"]:
        if matches_pattern(path, disallow_pattern):
            # Check if there is an explicit Allow override
            for allow_pattern in rules["allow"]:
                if matches_pattern(path, allow_pattern) and len(allow_pattern) >= len(disallow_pattern):
                    return True
            return False

    return True

def fetch_and_parse_robots(robots_url: str, target_ua: str) -> dict:
    rules = {"allow": [], "disallow": []}
    try:
        resp = requests.get(robots_url, headers={"User-Agent": target_ua}, timeout=8)
        if resp.status_code != 200:
            return rules

        current_ua_matches = False
        
        for line in resp.text.splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue

            if line.lower().startswith("user-agent:"):
                ua = line.split(":", 1)[1].strip()
                current_ua_matches = (ua == "*" or target_ua.lower() in ua.lower())

            elif current_ua_matches:
                if line.lower().startswith("allow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        rules["allow"].append(path)
                elif line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        rules["disallow"].append(path)

    except Exception as e:
        log.warning("Could not fetch robots.txt from %s: %s (defaulting to allow)", robots_url, e)

    return rules

def matches_pattern(path: str, pattern: str) -> bool:
    if not pattern:
        return False
    if pattern == "/":
        return path == "/"
    regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*")
    return bool(re.match(regex_pattern, path))
