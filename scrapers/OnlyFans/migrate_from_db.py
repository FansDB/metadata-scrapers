import os
from sqlite import get_rows

import config
stashconfig = config.stashconfig if hasattr(config, 'stashconfig') else {
    "scheme": "http",
    "Host":"localhost",
    "Port": "9999",
    "ApiKey": "",
}

try:
    import stashapi.log as log
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print("You need to install the stashapp-tools (stashapi) python module. (cmd): pip install stashapp-tools", file=sys.stderr)
    sys.exit()


stash = StashInterface(stashconfig)

if os.path.exists("sha-cache.db"):
    
    log.info("migrating sha256 values to fingerprints...")
    for sha256, oshash in get_rows():
        log.info(f"{sha256=} {oshash=}")
        
        scene = stash.find_scene_by_hash({"oshash":oshash}, fragment='id files { id fingerprint(type:"sha256") } ')
        if scene["files"][0]["fingerprint"]:
            return
        stash.file_set_fingerprints(scene["files"][0]["id"], {"type": "sha256", "value":sha256})

    os.rename("sha-cache.db", "sha-cache.db.old")