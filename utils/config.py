import yaml
import json
def readYaml(filename: str):
    with open(filename, "r") as f:
        return yaml.safe_load(f)

def readJson(filename: str):
    with open(filename, "r") as f:
        return json.load(f)
def getLanguageMetadata(lang: str):
    return readJson(f"lang/{lang}.json")