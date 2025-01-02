import re

dmRegex = r"\b(dm)(?:[\'\‘\’\`\"\“\”]*)(?:s?)\b"
triggerArray = [
    # DM / in your DMs
    "dm",
    "dms"
    "inbox",
    "messages"
    # sending
    "sending you",
    "sending this",
    # partial video
    "teaser",
    "snippet",
    "entire",
    "full video",
    "full vid",
    "full scene",
    # message prompts
    "with the message",
    "message me",
    "send me"
    # unlocking
    "unlock",
    "receive it",
    "purchase",
    # tipping
    "under this post",
    "tip",
    # rebill
    "rebills",
    "rebillers",
]

def findTrailerTrigger(oftitle):
    # check regex
    if re.search(dmRegex, oftitle, re.IGNORECASE):
        return True
    # check other regex array
    for trigger in triggerArray:
        triggerRegex = f"\b{trigger}\b"
        if re.search(triggerRegex, oftitle, re.IGNORECASE):
            return True
    return False