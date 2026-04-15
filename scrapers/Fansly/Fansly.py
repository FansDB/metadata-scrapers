import gzip
import json
import re
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

POST_URL_RE = re.compile(r"https?://coomer\.st/fansly/user/(\d+)/post/(\d+)")
FANSLY_POST_RE = re.compile(r"https?://(?:www\.)?fansly\.com/post/(\d+)")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Referer": "https://coomer.st",
    "Accept": "text/css",
}

def log_error(message: str) -> None:
    sys.stderr.write(message + "\n")

def fetch_json(url: str) -> dict:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as response:
        data = response.read()
        if response.info().get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))

def parse_date(published: str | None) -> str | None:
    if not published:
        return None

    value = published.strip()
    if value.endswith("Z"):
        value = value[:-1]

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    if "T" in value:
        return value.split("T", 1)[0]
    return value

def extract_url(operation: str, payload: dict) -> str | None:
    candidates: list[str] = []

    url = payload.get("url")
    if isinstance(url, str):
        candidates.append(url)

    if operation == "scene-by-fragment":
        urls = payload.get("urls") or []
        if isinstance(urls, list):
            candidates.extend(value for value in urls if isinstance(value, str))

    for value in candidates:
        if FANSLY_POST_RE.search(value):
            return value

    return None

def resolve_post_identifiers(scene_url: str) -> tuple[str, str] | None:
    match = FANSLY_POST_RE.search(scene_url)
    if not match:
        log_error(f"Could not parse Fansly post URL: {scene_url}")
        return None

    post_id = match.group(1)

    lookup_url = f"https://coomer.st/fansly/post/{post_id}"

    try:
        with urlopen(Request(lookup_url, headers=HEADERS), timeout=30) as response:
            resolved_url = response.geturl()
    except (HTTPError, URLError, TimeoutError) as err:
        log_error(f"Failed to resolve Fansly URL via Coomer: {err}")
        return None

    resolved_match = POST_URL_RE.search(resolved_url)
    if resolved_match:
        return resolved_match.groups()

    # Some Coomer responses keep the short URL and do not emit an HTTP redirect.
    # Fallback to API post lookup to resolve user_id (artist_id) from post_id.
    lookup_api_url = f"https://coomer.st/api/v1/fansly/post/{post_id}"
    try:
        lookup_data = fetch_json(lookup_api_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as err:
        log_error(f"Failed to resolve Coomer post identifiers via API: {err}")
        return None

    if isinstance(lookup_data, dict):
        user_id = lookup_data.get("artist_id")
        resolved_post_id = lookup_data.get("post_id")
        if user_id and resolved_post_id:
            return str(user_id), str(resolved_post_id)

    log_error(f"Resolved URL is not a Coomer Fansly user post URL: {resolved_url}")
    return None

def scene_from_url(scene_url: str) -> dict:
    identifiers = resolve_post_identifiers(scene_url)
    if not identifiers:
        return {}

    user_id, post_id = identifiers
    coomer_url = f"https://coomer.st/fansly/user/{user_id}/post/{post_id}"
    post_api_url = f"https://coomer.st/api/v1/fansly/user/{user_id}/post/{post_id}"
    profile_api_url = f"https://coomer.st/api/v1/fansly/user/{user_id}/profile"

    try:
        post_data = fetch_json(post_api_url)
        profile_data = fetch_json(profile_api_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as err:
        log_error(f"Failed to fetch Coomer API data: {err}")
        return {}

    post = post_data.get("post") if isinstance(post_data, dict) else {}
    studio_name = profile_data.get("name") if isinstance(profile_data, dict) else None

    result = {
        "urls": [scene_url, coomer_url],
        "studio": {"name": f"{studio_name} (Fansly)" if studio_name else ""},
    }

    if isinstance(post, dict):
        if title := post.get("title"):
            result["title"] = title
        if details := post.get("content"):
            result["details"] = details
        if date_value := parse_date(post.get("published")):
            result["date"] = date_value

    return result

def main() -> None:
    operation = sys.argv[1] if len(sys.argv) > 1 else ""
    if operation not in {"scene-by-url", "scene-by-fragment"}:
        log_error(f"Unsupported operation: {operation}")
        print(json.dumps({}))
        sys.exit(1)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as err:
        log_error(f"Invalid JSON input: {err}")
        print(json.dumps({}))
        sys.exit(1)

    url = extract_url(operation, payload if isinstance(payload, dict) else {})
    if not url:
        log_error(f"No scene URL found in payload for operation {operation}")
        print(json.dumps({}))
        return

    print(json.dumps(scene_from_url(url)))

if __name__ == "__main__":
    main()