from abc import ABC, abstractmethod
from rdflib import URIRef, Literal, BNode, Dataset, Graph
from SPARQLWrapper import SPARQLWrapper
import requests
from pyld import jsonld
from .errors import ServerError, ValidationError
from .walk import walk
from .validate import invalidIRI
from pyoxigraph import parse, RdfFormat


def jsonld2nt(doc, context):
    if type(doc) is list:
        for e in doc:
            e.pop("@context", None)
        doc = {"@context": context, "@graph": doc}
    else:
        doc["@context"] = context
    expanded = jsonld.expand(doc)
    return jsonld.to_rdf(expanded, options={'format': 'application/n-quads'})


PREFIXES = ("PREFIX dcat: <http://www.w3.org/ns/dcat#>\n"
            "PREFIX dct: <http://purl.org/dc/terms/>\n"
            "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n")


class AbstractTripleStore(ABC):
    @abstractmethod
    def query(self, query):
        pass

    @abstractmethod
    def update(self, query):
        pass

    def insert(self, graph, triples):
        query = "INSERT DATA { GRAPH <%s> { %s } }" % (graph, triples)
        return self.update(query)

    def remove(self, graph, triples):
        query = "DELETE DATA { GRAPH <%s> { %s } }" % (graph, triples)
        return self.update(query)

    def delete(self, graph, triples):
        query = "DELETE WHERE { GRAPH <%s> { %s } }" % (graph, triples)
        return self.update(query)

    # TODO: this is a hack and requires further investigation
    def delete_where(self, delete, where):
        query = "DELETE { %s } WHERE { %s }" % (delete, where)
        return self.update(query)

    def drop_graph(self, graph):
        return self.update(f"DROP GRAPH <{graph}>")

    @abstractmethod
    def store_file(self, graph, file):
        pass


class TripleStore(AbstractTripleStore):
    def __init__(self, api):
        self.api = api

    def __client(self, query):
        client = SPARQLWrapper(self.api, returnFormat='json')
        client.setQuery(PREFIXES + query)
        return client

    def query(self, query):
        client = self.__client(query)
        try:
            return client.queryAndConvert()["results"]["bindings"]
        except Exception as e:
            raise ServerError(f"SPARQL Query failed: {e}")

    def update(self, query):
        client = self.__client(query)
        client.method = 'POST'
        try:
            res = client.query()
            if res.response.code != 200:
                raise ServerError(f"HTTP Status code {res.response.code}")
        except Exception as e:
            raise ServerError(f"SPARQL UPDATE failed: {e}")

    def store_file(self, graph, file):
        headers = {"content-type": "text/turtle"}
        res = requests.put(f"{self.api}?graph={graph}",
                           data=open(file, 'rb'), headers=headers)
        return res.status_code == 200
        # TODO: detect error?


class NativeTripleStore(AbstractTripleStore):
    def __init__(self):
        self.ds = Dataset(default_union=True)

    def query(self, query):
        def term(t):
            if isinstance(t, URIRef):
                return {"type": "uri", "value": str(t)}
            if isinstance(t, BNode):
                return {"type": "bnode", "value": str(t)}
            literal = {"type": "literal", "value": str(t)}
            if t.language:
                literal["xml:lang"] = t.language
            if t.datatype:
                literal["datatype"] = str(t.datatype)
            return literal

        def map_row(row):
            return {str(k): term(v) for k, v in row.items()}

        query = PREFIXES + query
        return [map_row(row) for row in self.ds.query(query).bindings]

    def update(self, query):
        self.ds.update(PREFIXES + query)

    def drop_graph(self, graph):
        self.ds.remove_graph(graph)

    def store_file(self, graph, file):
        graph = self.ds.graph(graph)
        data = Graph()
        data.parse(file)
        # TODO with self.ds.transaction():
        for triple in data:
            graph.add(triple)
        return True


def createTripleStore(api):
    if (api):
        return TripleStore(api)
    else:
        return NativeTripleStore()


def sparql_to_rdf(binding):
    if binding['type'] == 'uri':
        return URIRef(binding['value'])
    elif binding['type'] == 'bnode':
        return BNode(binding['value'])
    elif binding['type'] == 'literal':
        if 'datatype' in binding:
            return Literal(binding['value'], datatype=URIRef(binding['datatype']))
        elif 'xml:lang' in binding:
            return Literal(binding['value'], lang=binding['xml:lang'])
        else:
            return Literal(binding['value'])


def result_to_ttl(data):
    rows = [dict([(key, sparql_to_rdf(val).n3())
                 for key, val in row.items()]) for row in data]
    return "\n".join([f"{row['s']} {row['p']} {row['o']} ." for row in rows])


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
