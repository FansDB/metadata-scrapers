import json
import re
import sys
from datetime import datetime

import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Referer': 'https://coomer.st',
    "Accept": 'text/css',
}
POST_URL_RE = re.compile(r"https?://coomer\.st/fansly/user/(\d+)/post/(\d+)")

def log_error(message: str) -> None:
    sys.stderr.write(message + "\n")

def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()

def extract_url(operation: str, payload: dict) -> str | None:
    if url := payload.get("url"):
        return url

    if operation == "scene-by-fragment":
        urls = payload.get("urls") or []
        if isinstance(urls, list):
            for value in urls:
                if isinstance(value, str) and "coomer.st/fansly/user/" in value and "/post/" in value:
                    return value

    return None

def scene_from_url(scene_url: str) -> dict:
    match = POST_URL_RE.search(scene_url)
    if not match:
        log_error(f"Could not parse Coomer Fansly post URL: {scene_url}")
        return {}

    user_id, post_id = match.groups()
    post_api_url = f"https://coomer.st/api/v1/fansly/user/{user_id}/post/{post_id}"
    profile_api_url = f"https://coomer.st/api/v1/fansly/user/{user_id}/profile"
    
    # errors raised in fetch_json
    post_data = fetch_json(post_api_url)
    profile_data = fetch_json(profile_api_url)

    post = post_data.get("post", {})
    studio_name = profile_data.get("name", {})

    result = {
        "urls": [scene_url],
        "studio": {"name": f"{studio_name} (Fansly)" if studio_name else ""},
    }
    
    date = datetime.strptime(post['published'], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')
    # fansly posts dont come with titles
    # result["title"] = post.get("title", "")
    result["details"] = post.get("content", "")
    result["date"] = date
    return result

def main():
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
