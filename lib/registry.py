from pathlib import Path
from datetime import datetime
from shutil import copy, copyfileobj, rmtree
import urllib
from .validate import validateJSON
from .rdf import jsonld2nt
from .rdffilter import RDFFilter
from .log import Log
from .errors import ApiError, NotFound, ValidationError
from .utils import read_json, write_json
from .formats import guess_format
import re


class Registry:
    context = None
    remote_contexts = {}
    schema = None
    auto_ids = True

    def __init__(self, kind, **config):
        self.base = config["base"]
        self.store = config["store"]
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
        if self.kind == "terminology":  # FIXME: this is ugly
            item["partOf"] = [{"uri": self.graph}]
        else:
            item["partOf"] = [self.graph]
        if self.schema:
            validateJSON(item, schema=self.schema)
        return item

    def list(self):
        files = [f for f in self.stage.iterdir() if f.suffix == ".json" and re.match('^[0-9]+$', f.stem)]
        return [read_json(f) for f in files]

    def count_registered(self):
        query = (f"SELECT (COUNT(*) AS ?count) FROM <{self.graph}>"
                 f"{{ ?s <http://purl.org/dc/terms/isPartOf> <{self.graph}> }}")
        return int(self.store.query(query, "rdflib")[0]["count"])

    def get(self, id):
        return read_json(self.stage / f"{int(id)}.json")

    def _save_record(self, data, id=None):
        data = self.validate(data, id)
        id = data["id"]
        write_json(self.stage / f"{id}.json", data)
        (self.stage / str(id)).mkdir(exist_ok=True)
        return data

    def register(self, data, id=None):
        data = self._save_record(data, id)
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
        # query issued statements to keep them
        query = f"SELECT * {{ GRAPH <{self.graph}> {{ VALUES (?p) {{(dct:issued)}} ?s ?p ?o }} }}"
        issued = self.store.query(query, "nq")
        # rebuild metadata from JSON-LD
        metadata = jsonld2nt(self.list(), self.context, self.remote_contexts)
        # add issued statements and modified timestamp
        modified = datetime.now().replace(microsecond=0).isoformat()
        file = self.stage / f"{self.kind}.ttl"
        with open(file, "w") as f:
            f.write(metadata)
            f.write(issued)
            f.write(
                f'\n<{self.graph}> '
                '<http://purl.org/dc/terms/modified> '
                f'"{modified}"^^'
                '<http://www.w3.org/2001/XMLSchema#dateTime> .'
            )
        self.store.store_file(self.graph, file)

    def delete(self, id):
        self.remove(id)
        (self.stage / f"{id}.json").unlink(missing_ok=False)
        rmtree(self.stage / str(id), ignore_errors=True)

    def purge(self):
        for id in [t["id"] for t in self.list()]:
            self.delete(id)

    def load(self, id, add=False):
        stage = self.stage / str(id)
        file = stage / f"{self.kind}-{id}.nt"
        uri = self.get(id)["uri"]
        if not file.is_file():
            raise NotFound(f"{self.kind} data has not been received!")
        log = Log(stage / "load.json",
                  f"Loading {self.kind} {uri} from {file}")
        if add:
            self.store.add_file(uri, file)
        else:
            self.store.store_file(uri, file)
        self.update_distribution(id, log)
        return log.done()

    def update_distribution(self, id, log, published=True):
        uri = self.get(id)["uri"]
        download = f"{self.graph}{id}/stage/{self.kind}-{id}.nt"

        self.store.delete(self.graph, f"<{uri}> dct:issued ?issued")

        # TODO: this requires further investigation: which graph to query?!
        self.store.delete_where(
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
            self.store.insert(self.graph, triples)
        else:
            log.append("Removed issued timestamp and distribution")

    def remove(self, id):
        uri = self.get(id)["uri"]
        rmtree(self.stage / str(id), ignore_errors=True)
        self.store.drop_graph(uri)
        self.update_distribution(id, Log("/dev/null"), False)

    def receive_log(self, id):
        return Log(self.stage / str(id) / "receive.json").load()

    def load_log(self, id):
        return Log(self.stage / str(id) / "load.json").load()

    def forbidden_namespaces(self, id):
        return {}

    def receive(self, id, source=None, format=None):
        item = self.get(id)

        if not source:
            source, format = self.identify_source(item, format)
        if not source:
            raise NotFound("Missing source to receive data from")

        format = guess_format(source, format=format)
        if not format:
            raise ApiError("Unknown data format")

        original, log = self.fetch_source(id, source, format)

        file = self.preprocess_source(id, original, format, log)
        self.receive_rdf(id, file, log)
        return log.done()

    def fetch_source(self, id, source, format):
        stage = self.stage / str(id)
        stage.mkdir(exist_ok=True)

        original = stage / f"original.{format}"
        log = Log(stage / "receive.json", f"Receiving {id} from {source}")

        try:
            if "/" not in source:   # file
                source = self.data / source
                log.append(f"Retrieving source {source} from data directory")
                copy(source, original)
            else:  # URL
                log.append(f"Retrieving source from {source}")
                # TODO: caching (download only if modified)
                with urllib.request.urlopen(source) as fsrc, open(original, 'wb') as fdst:
                    copyfileobj(fsrc, fdst)
        except Exception as e:
            log.done(f"Retrieving failed: {e}")
            raise NotFound(f"{source} not found")

        return (original, log)

    def preprocess_source(self, id, file, format, log):
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

    def identify_source(self, data, format):
        for dist in data.get("distributions", []):
            format = format or dist.get("format", None)
            if "download" in dist:
                return dist["download"], format
            elif dist.get("url", "").startswith("https://doi.org/10.5281/zenodo."):
                id = dist["url"][31:]
                return f"https://zenodo.org/api/records/{id}/files-archive", "zip"
        return None, None
