from pathlib import Path
import json
from .utils import read_json, read_context
from .rdffilter import RDFFilter
from .registry import Registry
from .errors import ValidationError

mappingProperties = [
    "http://www.w3.org/2004/02/skos/core#mappingRelation",
    "http://www.w3.org/2004/02/skos/core#closeMatch",
    "http://www.w3.org/2004/02/skos/core#exactMatch",
    "http://www.w3.org/2004/02/skos/core#broadMatch",
    "http://www.w3.org/2004/02/skos/core#narrowMatch",
    "http://www.w3.org/2004/02/skos/core#relatedMatch",
    "http://www.w3.org/2002/07/owl#sameAs",
    "http://www.w3.org/2002/07/owl#equivalentClass",
    "http://www.w3.org/2002/07/owl#equivalentProperty",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
]


def jskos_mapping_triples(mappings) -> list:
    try:
        for m in mappings:
            prop = next((p for p in m["type"] if p in mappingProperties), None)
            if not prop:
                continue
            f = m["from"].get("memberSet", [])
            t = m["to"].get("memberSet", [])
            if type(f) is not list or type(t) is not list or len(f) != 1 or len(t) != 1:
                continue
            yield f"<{f[0]['uri']}> <{prop}> <{t[0]['uri']}> .\n"
    except Exception:
        raise ValidationError("Failed to convert JSKOS mappings!")


class MappingRegistry(Registry):
    schema = read_json(Path(__file__).parent / 'mappings-schema.json')
    context = read_context("collection.json")

    def __init__(self, **config):
        super().__init__("mappings", **config)

    def process_jskos_mappings(self, source, target, log):
        log.append("Converting JSKOS mappings to RDF mapping triples")
        lines = [line for line in open(source)]
        target = open(target, "w")
        count = 0
        mappings = [json.loads(line) for line in lines]
        for triple in jskos_mapping_triples(mappings):
            target.write(triple)
            count = count + 1
        log.append(f"Processed {len(lines)} lines into {count} mappings")

    def preprocess_source(self, id, original, fmt, log):
        if fmt == "ndjson":
            result = self.stage / str(id) / "original.ttl"
            self.process_jskos_mappings(original, result, log)
            return result
        else:
            return original

    def rdf_filter(self, id):
        # TODO: extend filter if mapping is between specific terminologies
        return RDFFilter(allow_predicate=mappingProperties)

    def append(self, id, data):
        graph = self.get(id)["uri"]
        triples = "".join(*jskos_mapping_triples(json.loads(data)))
        self.store.insert(graph, triples)

    def detach(self, id, data):
        graph = self.get(id)["uri"]
        triples = "".join(*jskos_mapping_triples(json.loads(data)))
        self.store.delete(graph, triples)
