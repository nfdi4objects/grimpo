from abc import ABC, abstractmethod
from rdflib import URIRef, BNode, Dataset, Graph
from SPARQLWrapper import SPARQLWrapper
import requests
import warnings
from .errors import ServerError


def createTripleStore(api=None):
    if (api):
        return ExternalTripleStore(api)
    else:
        return InternalTripleStore()


class AbstractTripleStore(ABC):
    """
    Stores RDF 1.1 triples in a named graph with the default graph being the union
    graph. Provides method to read via SPARQL Query and to write with prepared statements.
    """

    """These are automatically prepended to every query."""
    prefixes = ("PREFIX dcat: <http://www.w3.org/ns/dcat#>\n"
                "PREFIX dct: <http://purl.org/dc/terms/>\n"
                "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n")

    """Must implement SPARQL Query"""
    @abstractmethod
    def query(self, query):
        pass

    """Import"""
    @abstractmethod
    def store_file(self, graph, file):
        pass

    """Must implement SPARQL Update. Not to be called directly."""
    @abstractmethod
    def _update(self, query):
        pass

    def insert(self, graph, triples):
        query = "INSERT DATA { GRAPH <%s> { %s } }" % (graph, triples)
        return self._update(query)

    def delete(self, graph, triples):
        query = "DELETE WHERE { GRAPH <%s> { %s } }" % (graph, triples)
        return self._update(query)

    # TODO: this is a hack and requires further investigation
    def delete_where(self, delete, where):
        query = "DELETE { %s } WHERE { %s }" % (delete, where)
        return self._update(query)

    def drop_graph(self, graph):
        return self._update(f"DROP GRAPH <{graph}>")


class ExternalTripleStore(AbstractTripleStore):
    """Triple store accessed via HTTP SPARQL API."""

    def __init__(self, api):
        self.api = api

    def __client(self, query):
        client = SPARQLWrapper(self.api, returnFormat='json')
        client.setQuery(self.prefixes + query)
        return client

    def query(self, query):
        client = self.__client(query)
        try:
            return client.queryAndConvert()["results"]["bindings"]
        except Exception as e:
            raise ServerError(f"SPARQL Query failed: {e}")

    def _update(self, query):
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


class InternalTripleStore(AbstractTripleStore):
    """In-Memory Triple Store"""

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

        query = self.prefixes + query

        # RDFLib raises warning, see <https://github.com/RDFLib/rdflib/issues/3361>
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return [map_row(row) for row in self.ds.query(query).bindings]

    def _update(self, query):
        self.ds.update(self.prefixes + query)

    def drop_graph(self, graph):
        self.ds.remove_graph(graph)

    def store_file(self, graph, file):
        graph = self.ds.graph(graph)
        data = Graph()
        data.parse(file)
        for triple in data:
            graph.add(triple)
        return True
