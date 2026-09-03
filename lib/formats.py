known_formats = {
    "https://format.gbv.de/rdf/xml": "xml",
    "https://format.gbv.de/rdf/turtle": "ttl",
    "https://format.gbv.de/rdf/ntriples": "nt",
    "https://format.gbv.de/zip": "zip",
    "https://format.gbv.de/ndjson": "ndjson",
    "https://format.gbv.de/json": "json",
    # TODO: Add BARTOC Format URIs
    # http://bartoc.org/en/Format/RDF
}


def guess_format(source, format=None):
    if format:
        if format in known_formats:
            return known_formats[format]
        elif format in known_formats.values():
            return format
    elif source:
        ext = source.split(".")[-1]
        if ext in ["nt", "ttl"]:
            return "ttl"
        elif ext in ["rdf", "xml"]:
            return "xml"
        elif ext in ["ndjson", "jsonl"]:
            return "ndjson"
        elif ext in ["json"]:
            return "json"
        elif ext in ["zip", "ZIP"]:
            return "zip"
