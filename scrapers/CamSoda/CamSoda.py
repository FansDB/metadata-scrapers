import sys
import json
import cloudscraper

def sceneByURL(url):
    # Extract the ID from the URL
    scene_id = url.rstrip('/').split('/')[-1]
    
    scraper = cloudscraper.create_scraper()
    resp = scraper.get(f"https://www.camsoda.com/api/v1/media/get/{scene_id}")
    data = resp.json()
    
    media = data.get("media", {})
    
    return {
        "title": media.get("name"),
        "details": media.get("description"),
        "date": media.get("created_at", "")[:10],
        "image": media.get("thumbnail_url"),
        "performers": [{"name": media.get("user_display_name")}],
        "studio": {"name": f"{media.get('username')} (CamSoda)"},        
        "urls": [url],
    }

if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    action = sys.argv[1]

    if action == "sceneByURL":
        result = sceneByURL(input_data["url"])
        print(json.dumps(result))