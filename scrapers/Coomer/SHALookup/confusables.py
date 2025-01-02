from characters import characters
from util import checkLNP, clean
import math

# The current cache of all the supported alphabet characters
alphabetMap = dict()

# The current cache of all the supported confusable characters
confusablesMap = dict()

for key, value in characters.items():
    alphabetMap[key] = value
    for char in value:
        confusablesMap[char] = key

# Removes confusable unicode characters from a string.
def remove(str):
    if checkLNP(str):
        return str;
    newStr = '';
    for char in clean(str):
        newStr += confusablesMap.get(char) or char
    return newStr;

# Randomly mixes up a string with random confusable characters.
def obfuscate(str):
    newStr = '';
    for char in str:
        charMap = alphabetMap.get(char);
        if (charMap):
            newStr += charMap[math.floor(math.random() * charMap.length)];
        else:
            newStr += char;
    return newStr;