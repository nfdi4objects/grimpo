from pyld import jsonld
from .errors import ValidationError
from .walk import walk
from .validate import invalidIRI
from pyoxigraph import parse, RdfFormat


def context_loader(documents):
    """Load allowlisted JSON-LD contexts from local documents only."""
    def load(url, options=None):
        if url not in documents:
            raise ValidationError(f"Unsupported remote JSON-LD context: {url}")
        return {
            "contentType": "application/ld+json",
            "contextUrl": None,
            "document": documents[url],
            "documentUrl": url,
        }
    return load


def jsonld2nt(doc, context, remote_contexts=None):
    """Convert JSON-LD to N-Quads without fetching remote contexts."""
    remote_contexts = remote_contexts or {}
    try:
        expanded = jsonld.expand(doc, options={
            "expandContext": context,
            "documentLoader": context_loader(remote_contexts)
        })
    except jsonld.JsonLdError as error:
        # PyLD wraps exceptions raised by document loaders.
        url = error.details.get("url")
        if error.code == "loading remote context failed" and url not in remote_contexts:
            raise ValidationError(
                f"Unsupported remote JSON-LD context: {url}")
        raise
    return jsonld.to_rdf(expanded, options={'format': 'application/n-quads'})


class NullLog:
    def append(self, msg):
        pass


def triple_iterator(source, log=NullLog()):
    """Recursively extract RDF triples from a file, directory and/or ZIP archive."""
    for file, path, archive in walk(source):
        if file.endswith(".ttl"):
            format = RdfFormat.TURTLE
        elif file.endswith(".nt"):
            format = RdfFormat.N_TRIPLES
        elif file.endswith(".rdf") or file.endswith(".xml"):
            format = RdfFormat.RDF_XML
        else:
            continue

        if archive:
            input = archive.open(file)
        else:
            input = open(file, "rb")

        base = f"file://{file}" if file.startswith("/") else f"file:{file}"

        # Check whether XML file is RDF/XML or any other XML
        if file.endswith(".xml"):
            # FIXME: this requires all XML inputs to be UTF-8, what about other encodings?!
            xml = input.read().decode('utf-8')
            if 'http://www.w3.org/1999/02/22-rdf-syntax-ns#' not in xml:
                continue
            input.seek(0)

        try:
            log.append(f"Extracting RDF from {base} as {format}")
            for triple in parse(input, format=format, base_iri=base, lenient=True, without_named_graphs=True):
                for x in ['subject', 'predicate', 'object']:
                    if invalidIRI(getattr(triple, x)):
                        raise ValidationError(f"{getattr(triple, x)} is no valid IRI")
                yield str(triple.subject), str(triple.predicate), str(triple.object)
        except Exception as e:
            error = e if type(e) is ValidationError else ValidationError.fromException(e)
            log.append(f"Error parsing {base}: {error}")
            nested = [*path, file]
            nested = nested[1:]
            for file in reversed(nested):
                error = error.wrapInFile(file)
            raise error
