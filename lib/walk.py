import os
from zipfile import ZipFile, ZipExtFile
from pathlib import Path


def isZip(file) -> bool:
    """Check whether given file looks like a ZIP archive."""
    return Path(file).suffix == ".zip" or Path(file).suffix == ".ZIP"


def zipwalk(file, path=None) -> list:
    """Recursively iterate ZIP archive contents."""
    name = file.name if isinstance(file, ZipExtFile) else file
    path = [name] if path is None else [*path, name]
    archive = ZipFile(file)
    infos = set(archive.infolist())
    dirs = {f.filename for f in infos if f.is_dir()}
    zips = {f.filename for f in infos} - dirs
    zips = {f for f in zips if isZip(f)}
    files = {f.filename for f in infos} - (zips | dirs)

    for name in files:
        yield name, path, archive

    for z in zips:
        with archive.open(z) as f:
            yield from zipwalk(f, path)


def walk(file) -> list:
    """Iterate over a file, recursing into contents of ZIP archives."""
    if os.path.isfile(file):
        if isZip(file):
            yield from zipwalk(file)
        else:
            yield str(file), [], None
    else:
        raise Exception(f"file not found: {file}")
