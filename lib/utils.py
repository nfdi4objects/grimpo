import json
import datahugger
from pathlib import Path
from .errors import NotFound


def read_json(file):
    try:
        with open(file) as f:
            return json.load(f)
    except Exception as e:
        raise NotFound(e)


def write_json(file, data):
    with open(file, "w") as f:
        f.write(json.dumps(data, indent=4))


def read_context(file):
    return read_json(Path(__file__).parent / "context" / file)


# TODO: limit to known formats
def access_location(data):
    # just get first
    for access in data.get("distributions", []):
        fmt = access.get("format", None)
        if "download" in access:
            return access["download"], fmt
        elif "url" in access:
            url = access["url"]
            try:
                info = datahugger.info(url)
                # TODO: try this
                print(info)
                return url, fmt
            except Exception:
                pass
    return None, None
