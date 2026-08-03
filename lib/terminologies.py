from pathlib import Path
import requests
import json
from .utils import read_json
from .errors import NotFound
from .rdf import jsonld2nt
from .registry import Registry

JSKOS_CONTEXT_URL = "https://gbv.github.io/jskos/context.json"


class TerminologyRegistry(Registry):
    context = read_json(Path(__file__).parent / 'jskos-context.json')
    remote_contexts = {JSKOS_CONTEXT_URL: context}
    skosmos_context = read_json(Path(__file__).parent / 'skosmos-context.json')
    auto_ids = False

    def __init__(self, **config):
        super().__init__("terminology", prefix="http://bartoc.org/en/node/", **config)

    def namespaces(self):
        namespaces = {}
        for voc in self.list():
            if "namespace" in voc:
                namespaces[voc["uri"]] = voc["namespace"]
        return namespaces

    def skosmos(self):
        ttl = ""
        for voc in self.list():
            file = self.stage / voc["id"] / "skosmos.ttl"
            if file.is_file():
                ttl = ttl + file.read_text()

        return ttl

    def _resolve(self, item):
        item = self.validate(item)
        id = str(int(item["id"]))
        uri = f"{self.prefix}{id}"

        bartoc = Path(self.data) / 'bartoc.json'
        if bartoc.is_file():
            voc = [v for v in read_json(bartoc) if v["uri"] == uri]
        else:
            voc = requests.get(f"https://bartoc.org/api/data?uri={uri}").json()

        if not len(voc):
            raise NotFound(f"Terminology not found: {uri}")

        data = self.validate(voc[0], id)
        jsonld2nt(data, self.context, self.remote_contexts)
        return data

    def register(self, item):
        data = self._resolve(item)
        return super().register(data, data["id"])

    def replace(self, items):
        if type(items) is not list:
            return super().replace(items)

        records = [self._resolve(item) for item in items]

        self.purge()
        for record in records:
            self._save_record(record, record["id"])
        self.update_metadata()
        return self.list()

    def update_distribution(self, id, log, published=True):
        super().update_distribution(id, log, published)

        stage = self.stage / str(id)
        if not stage.is_dir():
            return

        skosmos = stage / "skosmos.ttl"
        voc = self.get(id)
        query = "SELECT * { GRAPH <%s> { ?voc a <%s> } } LIMIT 1" \
            % (voc['uri'], 'http://www.w3.org/2004/02/skos/core#ConceptScheme')
        if not (voc.get("languages", []) and self.sparql.query(query)):
            if skosmos.is_file():
                skosmos.unlink()
            return

        voc["a"] = ["skosmos:Vocabulary", "void:Dataset"]
        voc["id"] = f"{self.graph}{id}/stage/skosmos.ttl#{id}"
        if "@context" in voc:
            voc["@context"] = [voc["@context"], self.skosmos_context]
        with open(skosmos, "w") as f:
            ttl = jsonld2nt(voc, self.skosmos_context, self.remote_contexts)
            ttl = "\n".join(sorted(ttl.rstrip().split("\n")))
            f.write(ttl)

    def preprocess_source(self, id, original, fmt, log):
        if fmt == "ndjson":
            log.append("Converting JSKOS to RDF")
            with open(original) as file:
                jskos = [json.loads(line) for line in file]
            rdf = jsonld2nt(jskos, self.context, self.remote_contexts)
            original = self.stage / str(id) / "original.ttl"
            with open(original, "w") as f:
                f.write(rdf)

        return original

    def forbidden_namespaces(self, id):
        namespaces = dict(self.namespaces())
        namespaces.pop(f"{self.prefix}{id}", None)
        return namespaces
