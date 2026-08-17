# Unit test
import pytest
from lib.triplestores import createTripleStore
from rdflib import URIRef, Literal, BNode
from werkzeug import Request
from werkzeug.test import EnvironBuilder


def test_store():
    store = createTripleStore()

    store.insert('http://example.org/', '_:b1 dct:title "foo"')
    assert store.query("SELECT * { ?s ?p ?o }") == [{
        's': {'type': 'bnode', 'value': 'b1'},
        'p': {'type': 'uri', 'value': 'http://purl.org/dc/terms/title'},
        'o': {'type': 'literal', 'value': 'foo'}
    }]
    assert store.query("SELECT * { ?s ?p ?o }", "rdflib") == [{
        's': BNode('b1'),
        'p': URIRef('http://purl.org/dc/terms/title'),
        'o': Literal("foo")
    }]
    assert store.query("SELECT * { ?s ?p ?o }", "n3") == [{
        's': '_:b1',
        'p': '<http://purl.org/dc/terms/title>',
        'o': '"foo"'
    }]
    assert store.query("SELECT * { ?s ?p ?o }", "nq") == '_:b1 <http://purl.org/dc/terms/title> "foo" .'

    store.store_file('http://example.org/1', "tests/filter.ttl")
    query = "SELECT * { GRAPH <http://example.org/1> { ?s ?b ?o } }"
    assert len(store.query(query)) == 6

    store.store_file('http://example.org/2', "tests/ex1.ttl")
    query = "SELECT * { GRAPH <http://example.org/2> { ?s ?b ?o } }"
    assert len(store.query(query)) == 3

    store.add_file('http://example.org/2', "tests/ex2.ttl")
    query = "SELECT * { GRAPH <http://example.org/2> { ?s ?b ?o } }"
    assert len(store.query(query)) == 5

    # SPARQL query endpoint
    def sparql(*args, **kwargs):
        env = EnvironBuilder('/', None, *args, **kwargs)
        req = Request(env.get_environ())
        return store.query_request(req)

    with pytest.raises(Exception):
        sparql({"query": ""})
    with pytest.raises(Exception):
        sparql({"query": "?"})

    res = sparql({"query": query}).json
    assert res["head"] == {"vars": ["s", "b", "o"]}
    assert len(res["bindings"]) == 5

    res = sparql(data="DESCRIBE <http://example.org/NULL>",
                 content_type="application/sparql-query", method="POST").json
    assert res == {"head": {"vars": []}, "bindings": []}

    # TODO: content-type="application/x-www-form-urlencoded", method="POST")
