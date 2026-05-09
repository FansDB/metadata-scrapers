import configparser
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, "..")
from py_common import log
import requests

FANSLY_API  = "https://apiv3.fansly.com/api/v1"
SCRIPT_DIR  = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")

DEFAULT_CONFIG = """[FanslyAPI]
# Session token for Fansly API.
# Get it from: F12 -> Network -> any apiv3.fansly.com request -> look for sessionToken query param
# Paste just the token value (without "sessionToken=")
session_token =
"""


def get_token():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            f.write(DEFAULT_CONFIG)
        log.info(f"Created config.ini at {CONFIG_FILE} - add your Fansly session_token")
        return None

    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE)
    token = config.get("FanslyAPI", "session_token", fallback="").strip()
    if not token:
        log.warning("No session_token set in config.ini - API requests may fail or return limited data")
        return None
    return token


def api_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://fansly.com",
        "Referer": "https://fansly.com/",
    }


def api_get(path, token=None):
    url = f"{FANSLY_API}/{path}"
    if token:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sessionToken={token}"
    log.info(f"GET {url}")
    r = requests.get(url, headers=api_headers(), timeout=15)
    if not r.ok:
        log.error(f"HTTP {r.status_code} for {url}: {r.text[:200]}")
        sys.exit(1)
    return r.json()


def parse_tags_from_content(content):
    """Extract #hashtags from post content, return (clean_details, tags)."""
    if not content:
        return "", []

    tags = []
    seen = set()
    for m in re.finditer(r'#(\w+)', content):
        name = m.group(1)
        if name.lower() not in seen:
            seen.add(name.lower())
            tags.append({"name": name})

    # Strip hashtags from end of content for clean details
    details = re.sub(r'\s*#\w+', '', content).strip()
    return details, tags


def find_image(data, key="media"):
    """
    Walk the response looking for a usable image URL.
    Fansly nests media differently depending on post type.
    """
    # Try accountMedia first
    for am in data.get("response", {}).get("accountMedia", []):
        media = am.get("media", {})
        # Try variants first (higher quality)
        for variant in media.get("variants", []):
            for loc in variant.get("locations", []):
                url = loc.get("location", "")
                if url:
                    return url
        # Fall back to direct locations
        for loc in media.get("locations", []):
            url = loc.get("location", "")
            if url:
                return url

    # Try preview media
    for pm in data.get("response", {}).get("accountMediaBundles", []):
        for am in pm.get("accountMedia", []):
            media = am.get("media", {})
            for loc in media.get("locations", []):
                url = loc.get("location", "")
                if url:
                    return url

    return None


def scrape_scene(post_id, token):
    data = api_get(f"post?ids={post_id}&ngsw-bypass=true", token)
    resp = data.get("response", {})

    posts = resp.get("posts", [])
    if not posts:
        log.error(f"No post found for id {post_id}")
        sys.exit(1)

    post     = posts[0]
    accounts = resp.get("accounts", [])
    account  = accounts[0] if accounts else {}

    content  = post.get("content", "") or ""
    details, tags = parse_tags_from_content(content)

    # Title = first line of content
    title = content.split("\n")[0].strip()
    # Strip hashtags from title too
    title = re.sub(r'\s*#\w+', '', title).strip() or f"Post {post_id}"

    scrape = {}
    scrape["title"]   = title
    scrape["details"] = details
    scrape["code"]    = str(post.get("id", post_id))

    # Date
    created_at = post.get("createdAt")
    if created_at:
        try:
            scrape["date"] = datetime.fromtimestamp(
                int(created_at), tz=timezone.utc
            ).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Image
    image = find_image(data)
    if image:
        scrape["image"] = image

    # Tags
    if tags:
        scrape["tags"] = tags

    # Performer
    username = account.get("username", "")
    if username:
        scrape["performers"] = [{"name": username}]

    # Studio
    if username:
        scrape["studio"] = {
            "name": f"{username} (Fansly)",
            "url":  f"https://fansly.com/{username}",
        }

    scrape["urls"] = [f"https://fansly.com/post/{post_id}"]
    return scrape


def scrape_performer_by_name(name, token):
    data = api_get(f"account?usernames={name}&ngsw-bypass=true", token)
    accounts = data.get("response", [])
    if not accounts:
        return []

    results = []
    for acc in accounts:
        p = build_performer(acc)
        if p:
            results.append(p)
    return results


def scrape_performer_by_url(url, token):
    m = re.match(r'^https?://fansly\.com/([^/?#]+)', url)
    if not m:
        log.error(f"Could not parse username from URL: {url}")
        sys.exit(1)
    username = m.group(1)
    data = api_get(f"account?usernames={username}&ngsw-bypass=true", token)
    accounts = data.get("response", [])
    if not accounts:
        log.error(f"No account found for {username}")
        sys.exit(1)
    return build_performer(accounts[0])


def build_performer(acc):
    if not acc:
        return None
    username = acc.get("username", "")
    scrape = {}
    scrape["name"]    = username
    scrape["aliases"] = acc.get("displayName", "")
    scrape["details"] = acc.get("about", "")
    scrape["country"] = acc.get("location", "")
    if username:
        scrape["urls"] = [f"https://fansly.com/{username}/posts"]

    # Avatar image
    avatar = acc.get("avatar", {}) or {}
    for loc in avatar.get("locations", []):
        url = loc.get("location", "")
        if url:
            scrape["image"] = url
            break

    return scrape


if __name__ == "__main__":
    fragment = json.loads(sys.stdin.read())

    token = get_token()
    mode  = sys.argv[1] if len(sys.argv) > 1 else "scene"

    if mode == "performer_name":
        name = fragment.get("name", "")
        results = scrape_performer_by_name(name, token)
        print(json.dumps(results))

    elif mode == "performer_url":
        url = fragment.get("url", "")
        result = scrape_performer_by_url(url, token)
        print(json.dumps(result))

    else:
        # Scene by URL
        url = fragment.get("url", "")
        m = re.search(r'/post/(\d+)', url)
        if not m:
            log.error(f"Could not parse post ID from URL: {url}")
            sys.exit(1)
        post_id = m.group(1)
        result = scrape_scene(post_id, token)
        print(json.dumps(result))