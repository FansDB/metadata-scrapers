# stdlib
import time
from datetime import datetime
import hashlib
from html import unescape
import json
import logging
import os
from pathlib import Path
import re
import sys
# local modules
from confusables import remove
from oftitle import findTrailerTrigger

# try importing config
import config
stashconfig = config.stashconfig if hasattr(config, 'stashconfig') else {
    "scheme": "http",
    "Host":"localhost",
    "Port": "9999",
    "ApiKey": "",
}
success_tag = config.success_tag if hasattr(config, 'success_tag') else "SHA: Match"
failure_tag = config.failure_tag if hasattr(config, 'failure_tag') else "SHA: No Match"

VERSION = "1.6.0"
MAX_TITLE_LENGTH = 64

# pip modules
try:
    import stashapi.log as log
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print("You need to install the stashapp-tools (stashapi) python module. (cmd): pip install stashapp-tools", file=sys.stderr)
    sys.exit()
try:
    import emojis
except ModuleNotFoundError:
    log.error("You need to install the emojis module. (https://pypi.org/project/emojis/)")
    log.error("If you have pip (normally installed with python), run this command in a terminal (cmd): pip install emojis")
    sys.exit()
try:
    import requests
except ModuleNotFoundError:
    log.error("You need to install the requests module. (https://docs.python-requests.org/en/latest/user/install/)")
    log.error("If you have pip (normally installed with python), run this command in a terminal (cmd): pip install requests")
    sys.exit()
try:
    from lxml import html
except ModuleNotFoundError:
    log.error("You need to install the lxml module. (https://lxml.de/installation.html#installation)")
    log.error("If you have pip (normally installed with python), run this command in a terminal (cmd): pip install lxml")
    sys.exit()

# calculate sha256
def compute_sha256(file_name):
    hash_sha256 = hashlib.sha256()
    with open(file_name, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def sha_file(file):
    try:
        return compute_sha256(file['path'])
    except FileNotFoundError:
        try:
            log.debug(f"file path: {file['path']}")
            # try looking in relative path
            # move up two directories from /scrapers/SHALookup
            newpath = os.path.join(Path.cwd().parent.parent, file['path'])
            return compute_sha256(newpath)
        except FileNotFoundError:
            log.error("File not found. Check if the file exists and is accessible.")
            print("null")
            sys.exit()

# get post
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Referer': 'https://coomer.su/search_hash'
}

# define stash globally
stash = StashInterface(stashconfig)

def add_sha256(sha256, oshash):
    scene = stash.find_scene_by_hash({"oshash":oshash}, fragment='id files { id fingerprint(type:"sha256") } ')
    if scene["files"][0]["fingerprint"]:
        return
    stash.file_set_fingerprints(scene["files"][0]["id"], {"type": "sha256", "value":sha256})


def getPostByHash(hash):
    for attempt in range(1, 5):
        shares = requests.get('https://coomer.su/api/v1/search_hash/' + hash, headers=headers, timeout=10)
        if shares.status_code == 200:
            break
        log.debug(f"Request status code: {shares.status_code}")
        time.sleep(2)
    shares.raise_for_status()
    data = shares.json()
    if (shares.status_code == 404 or len(data) == 0):
        log.debug("No results found")
        return None
    # construct url to fetch from API
    post = data['posts'][0]
    path = f'https://coomer.su/api/v1/{post["service"]}/user/{post["user"]}/post/{post["id"]}'
    # fetch post
    postres = requests.get(path, headers=headers)
    if postres.status_code == 404:
        log.error("Post not found")
        sys.exit(1)
    elif not postres.status_code == 200:
        log.error(f"Request failed with status code {postres.status}")
        sys.exit(1)
    scene = postres.json()
    scene = scene["post"]
    return splitLookup(scene, hash)

def splitLookup(scene, hash):
    if (scene['service'] == "fansly"):
        return parseFansly(scene, hash)
    else:
        return parseOnlyFans(scene, hash)

def searchPerformers(scene):
    pattern = re.compile(r"(?:^|\s)@([\w\-\.]+)")
    content = unescape(scene['content'])
    # if title is truncated, remove trailing dots and skip searching title
    if scene['title'].endswith('..') and scene['title'].removesuffix('..') in content:
        searchtext = content
    else:
        # if title is unique, search title and content
        searchtext = scene['title'] + " " + content
    usernames = re.findall(pattern,unescape(searchtext))
    return usernames

# from dolphinfix
def truncate_title(title, max_length):
    # Check if the title is already under max length
    if len(title) <= max_length:
        return title
    last_punctuation_index = -1
    punctuation_chars = {'.', '!', '?', '❤', '☺'}
    punctuation_chars.update(emojis.get(title))
    for c in punctuation_chars:
        last_punctuation_index = max(title.rfind(c, 0, max_length), last_punctuation_index)
    if last_punctuation_index != -1:
        return title[:last_punctuation_index+1]
    # Find the last space character before max length
    last_space_index = title.rfind(" ",0, max_length)
    # truncate at last_space_index if valid, else max_length
    title_end = last_space_index if last_space_index != -1 else max_length
    return title[:title_end]

def normalize_title(title):
    unconfused = remove(title)
    return unconfused.strip()

# from dolphinfix
def format_title(description, username, date):
    firstline = description.split("\n")[0].strip().replace("<br />", "")
    formatted_title = truncate_title(
        normalize_title(firstline), MAX_TITLE_LENGTH
    )
    if not len(description): # no description, return username and date
        return username + " - " + date
    elif len(formatted_title) <= 5: # title too short, add date
        return formatted_title + " - " + date
    elif not bool(re.search("[A-Za-z0-9]", formatted_title)): # textless, truncate and add date
        # decrease MAX_TITLE_LENGTH further to account for " - YYYY-MM-DD"
        return truncate_title(formatted_title, MAX_TITLE_LENGTH - 13) + " - " + date
    else:
        return formatted_title

def parseAPI(scene, hash):
    date = datetime.strptime(scene['published'], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')
    result = {}
    scene['content'] = unescape(scene['content']).replace("<br />", "\n")
    # title parsing
    result['Details'] = scene['content']
    result['Date'] = date
    result['Studio'] = {}
    result['Performers'] = []
    result['Tags'] = []
    # parse usernames
    usernames = searchPerformers(scene)
    log.debug(f"{usernames=}")
    for name in list(set(usernames)):
        name = name.strip('.') # remove trailing full stop
        result['Performers'].append({'Name': getnamefromalias(name)})
    # figure out multi-part scene
    # create array with file and attachments
    if (scene['file']):
        files = [scene['file']] + scene['attachments']
    else:
        files = scene['attachments']
    # only include videos
    files = [file for file in files if file['path'].endswith(".m4v") or file['path'].endswith(".mp4")]
    for i, file in enumerate(files):
        if hash in file['path']:
            scene['part'] = i + 1
    scene['total'] = len(files)
    # add studio in specific function
    return result, scene

# alias search
def getnamefromalias(alias):
    perfs = stash.find_performers( f={"aliases":{"value": alias, "modifier":"EQUALS"}}, filter={"page":1, "per_page": 5}, fragment= "name" )
    log.debug(perfs)
    if len(perfs):
        return perfs[0]['name']
    return alias

def getFanslyUsername(id):
    res = requests.get(f"https://coomer.su/api/v1/fansly/user/{id}/profile", headers=headers)
    if not res.status_code == 200:
        log.error(f"Request failed with status code {res.status}")
        sys.exit(1)
    profile = res.json()
    return profile["name"]

# if fansly
def parseFansly(scene, hash):
    # fetch scene
    result, scene = parseAPI(scene, hash)
    # look up performer username
    username = getFanslyUsername(scene['user'])
    result['Title'] = format_title(result['Details'], username, result['Date'])
    # add part on afterwards
    if scene['total'] > 1:
        result['Title'] += f" {scene['part']}/{scene['total']}"
    # craft fansly URL
    result['URL'] = f"https://fansly.com/post/{scene['id']}"
    # add studio and performer
    result['Studio']['Name'] = f"{username} (Fansly)"
    result['Performers'].append({ 'Name': getnamefromalias(username) })
    # Add trailer if hash matches preview
    for attachment in scene['attachments']:
        if 'preview' in attachment['name'] and hash in attachment['path']:
            result['Tags'].append({ "Name": 'Trailer' })
            break
    return result

# if onlyfans
def parseOnlyFans(scene, hash):
    # fetch scene
    result, scene = parseAPI(scene, hash)
    username = scene['user']
    result['Title'] = format_title(result['Details'], username, result['Date'])
    # add part on afterwards
    if scene['total'] > 1:
        result['Title'] += f" {scene['part']}/{scene['total']}"
    # craft OnlyFans URL
    result['URL'] = f"https://onlyfans.com/{scene['id']}/{username}"
    # add studio and performer
    result['Studio']['Name'] = f"{username} (OnlyFans)"
    result['Performers'].append({ 'Name': getnamefromalias(username) })
    # add trailer tag if contains keywords
    if findTrailerTrigger(result['Details']):
        result['Tags'].append({ "Name": 'Trailer' })
    return result

def hash_file(file):
    fingerprints = file['fingerprints']
    if sha256_fp := [fp for fp in fingerprints if fp['type'] == 'sha256']:
        log.debug("Found in fingerprints")
        return sha256_fp[0]['value']
    else:
        log.debug("Not found in fingerprints")
        oshash = [fp for fp in fingerprints if fp['type'] == 'oshash'][0]['value']
        sha256 = sha_file(file)
        add_sha256(sha256, oshash)
        return sha256

def check_video_vertical(scene):
    file = scene['files'][0]
    ratio = file['height'] / file['width']
    return ratio >= 1.5

def scrape():
    FRAGMENT = json.loads(sys.stdin.read())
    SCENE_ID = FRAGMENT.get('id')
    nomatch_id = stash.find_tag(failure_tag, create=True).get('id')
    success_id = stash.find_tag(success_tag, create=True).get('id')
    scene = stash.find_scene(SCENE_ID)
    if not scene:
        log.error("Scene not found - check your config.py file")
        sys.exit(1)
    result = None
    for f in scene['files']:
        hash = hash_file(f)
        log.debug(hash)
        result = getPostByHash(hash)
        if result is not None:
            break
    # if no result, add "SHA: No Match tag"
    if (result == None or not result['Title'] or not result['URL']):
        stash.update_scenes({
            'ids': [SCENE_ID],
            'tag_ids': {
                'mode': 'ADD',
                'ids': [nomatch_id]
            }
        })
        return None
    # check if scene is vertical
    if check_video_vertical(scene):
        result['Tags'].append({ 'Name': 'Vertical Video' })
    # if result, add tag
    result['Tags'].append({ 'Name': success_tag })
    return result

def main():
    try:
        result = scrape()
        print(json.dumps(result))
        log.exit("Plugin exited normally.")
    except Exception as e:
        log.error(e)
        logging.exception(e)
        log.exit("Plugin exited with an exception.")

if __name__ == '__main__':
    main()

# by Scruffy, feederbox826
# Last Updated 2023-12-14
