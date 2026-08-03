from pathlib import Path
from datetime import datetime
from shutil import copy, copyfileobj, rmtree
import urllib
from .validate import validateJSON
from .rdf import jsonld2nt
from .rdffilter import RDFFilter
from .log import Log
from .errors import ApiError, NotFound, ValidationError
from .utils import read_json, write_json, access_location
import re


class Registry:
    context = None
    remote_contexts = {}
    schema = None
    auto_ids = True

    def __init__(self, kind, **config):
        self.base = config["base"]
        self.sparql = config["store"]
        self.kind = kind
        # named graphs
        self.graph = f"{self.base}{kind}/"
        self.prefix = config.get("prefix", self.graph)
        # directories
        self.stage = Path(config.get("stage", "stage")) / kind
        self.stage.mkdir(exist_ok=True, parents=True)
        self.data = Path(config.get("data", "data"))
        self.data.mkdir(exist_ok=True, parents=True)

    def validate(self, item, id=None):
        if type(item) is not dict:
            raise ValidationError("expected JSON object")
        item = item.copy()

        if id:
            id = str(id)
            if item.get("id", id) != id:
                raise ValidationError(f"ids {id} and {item['id']} don't match")
        else:
            id = item.get("id", None)

        if id and "uri" in item:
            if item["uri"] != self.prefix + id:
                raise ValidationError(f"URI {item['uri']} and id {id} don't match")
        elif "uri" in item:
            id = item["uri"][len(self.prefix):]
            if not (item["uri"].startswith(self.prefix) and re.match('^[1-9]?[0-9]+$', id)):
                raise ValidationError(f"malformed URI: {item['uri']}")

        if not id:
            if self.auto_ids:
                items = self.list()
                id = str(max(int(c["id"]) for c in items) + 1 if items else 1)
            else:
                raise ValidationError("Missing uri or id")

        item["id"] = id
        item["uri"] = self.prefix + id
        item["partOf"] = [self.graph]
        if self.schema:
            validateJSON(item, schema=self.schema)
        return item

    def list(self):
        if not self.stage.is_dir():
            return []
        files = [f for f in self.stage.iterdir() if f.suffix == ".json" and re.match('^[0-9]+$', f.stem)]
        return [read_json(f) for f in files]

    def get(self, id):
        return read_json(self.stage / f"{int(id)}.json")

    def register(self, data, id=None):
        data = self.validate(data, id)
        id = data["id"]
        write_json(self.stage / f"{id}.json", data)
        (self.stage / str(id)).mkdir(exist_ok=True)
        self.update_metadata()
        return data

    def replace(self, items):
        if type(items) is not list:
            raise ValidationError(f"expected list of {self.kind}")
        [self.validate(x) for x in items]  # first check
        self.purge()
        for item in items:
            self.register(self.validate(item))  # then add
        return self.list()

    def update_metadata(self):
        query = f"SELECT * {{ GRAPH <{self.graph}> {{ VALUES (?p) {{(dct:issued)}} ?s ?p ?o }} }}"
        issued = self.sparql.query(query, "nq")
        metadata = jsonld2nt(self.list(), self.context, self.remote_contexts)
        file = self.stage / f"{self.kind}.ttl"
        with open(file, "w") as f:
            f.write(metadata)
            f.write(issued)
        self.sparql.store_file(self.graph, file)

    def delete(self, id):
        self.remove(id)
        (self.stage / f"{id}.json").unlink(missing_ok=False)
        rmtree(self.stage / str(id), ignore_errors=True)

    def purge(self):
        for id in [t["id"] for t in self.list()]:
            self.delete(id)

    def load(self, id, **kw):
        mode = kw.get('mode', 'replace')
        stage = self.stage / str(id)
        file = stage / f"{self.kind}-{id}.nt"
        uri = self.get(id)["uri"]
        if not file.is_file():
            raise NotFound(f"{self.kind} data has not been received!")
        log = Log(stage / "load.json",
                  f"Loading {self.kind} {uri} from {file}")
        if mode == 'add':
            self.sparql.add_file(uri, file)
        else:
            self.sparql.store_file(uri, file)
        self.update_distribution(id, log)
        return log.done()

    def update_distribution(self, id, log, published=True):
        uri = self.get(id)["uri"]
        download = f"{self.graph}{id}/stage/{self.kind}-{id}.nt"

        self.sparql.delete(self.graph, f"<{uri}> dct:issued ?issued")

        # TODO: this requires further investigation: which graph to query?!
        self.sparql.delete_where(
            "<%s> dcat:distribution ?s. ?s ?p ?o" % (uri),
            "<%s> dcat:distribution ?s . ?s dcat:downloadURL <%s>" % (uri, download))

        if published:
            log.append("Update issued timestamp and distribution")
            issued = datetime.now().replace(microsecond=0).isoformat()
            triples = "\n".join([
                f'<{uri}> dct:issued "{issued}"^^xsd:dateTime .',
                f'<{uri}> dcat:distribution [',
                f"dcat:accessURL <{uri}> ;",
                f"dcat:downloadURL <{download}> ;",
                f'dct:issued "{issued}"^^xsd:dateTime ;',
                "dcat:mediaType <https://www.iana.org/assignments/media-types/application/n-triples> ;",
                "dct:format <http://publications.europa.eu/resource/authority/file-type/RDF_N_TRIPLES> ",
                # TODO: dct:license and dct:modified ?
                # TODO: dcat:byteSize
                "]"
            ])
            self.sparql.insert(self.graph, triples)
        else:
            log.append("Removed issued timestamp and distribution")

    def remove(self, id):
        uri = self.get(id)["uri"]
        rmtree(self.stage / str(id), ignore_errors=True)
        self.sparql.drop_graph(uri)
        self.update_distribution(id, Log("/dev/null"), False)

    def receive_log(self, id):
        return Log(self.stage / str(id) / "receive.json").load()

    def load_log(self, id):
        return Log(self.stage / str(id) / "load.json").load()

    def forbidden_namespaces(self, id):
        return {}

    def receive(self, id, file=None):
        file, fmt = self.identify_source(id, file)
        original, log = self.fetch_source(id, file, fmt)
        file = self.preprocess_source(id, original, fmt, log)
        self.receive_rdf(id, file, log)
        return log.done()

    def identify_source(self, id, source=None):
        item = self.get(id)
        fmt = None

        if not source:
            source, fmt = access_location(item)
        if not source:
            raise NotFound("Missing source to receive data from")

        if fmt:
            fmt = fmt.removeprefix("https://format.gbv.de/")
            if fmt == "rdf/turtle":
                fmt = "ttl"
            elif fmt == "rdf/xml":
                fmt = "xml"

        if not fmt:
            if Path(source).suffix in [".nt", ".ttl"]:
                fmt = "ttl"
            elif Path(source).suffix in [".rdf", ".xml"]:
                fmt = "xml"
            elif Path(source).suffix in [".ndjson", ".jsonl"]:
                fmt = "ndjson"
            elif Path(source).suffix in [".zip", ".ZIP"]:
                fmt = "zip"

        if not fmt:
            raise ApiError("Unknown data format")

        return source, fmt

    def fetch_source(self, id, source, fmt):
        stage = self.stage / str(id)
        stage.mkdir(exist_ok=True)

        original = stage / f"original.{fmt}"
        log = Log(stage / "receive.json", f"Receiving {id} from {source}")

        try:
            if "/" not in source:
                source = self.data / source
                log.append(f"Retrieving source {source} from data directory")
                copy(source, original)
            else:
                # TODO: source may be a DOI or similar identifier
                # ./extract-rdf.py $download_dir $stage/triples.nt
                log.append(f"Retrieving source from {source}")
                # TODO: caching (download only if modified)
                with urllib.request.urlopen(source) as fsrc, open(original, 'wb') as fdst:
                    copyfileobj(fsrc, fdst)
        except Exception as e:
            log.done(f"Retrieving failed: {e}")
            raise NotFound(f"{source} not found")

        return (original, log)

    def preprocess_source(self, id, file, fmt, log):
        """Returned file must be RDF or ZIP (with RDF)."""
        return file

    def rdf_filter(self, id):
        namespaces = tuple(list(self.forbidden_namespaces(id).values()))
        return RDFFilter(disallow_subject_ns=namespaces)

    def receive_rdf(self, id, source, log):
        stage = self.stage / str(id)
        keep = open(stage / f"{self.kind}-{id}.nt", "w")
        remove = open(stage / f"{self.kind}-{id}-removed.nt", "w")

        kept, removed, changed = self.rdf_filter(id).process(source, keep, remove, log)
        # TODO: if keptCount is zero, raise an error
