import json
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
