# Integration test
from unittest.mock import patch
import os
from urllib.parse import urlparse, parse_qs
from shutil import copy
from pathlib import Path
import pytest
import jsonschema

from lib import read_json
from app import app, configure

data = Path(__file__).parent / "data"

sparqlApi = os.getenv('SPARQL')

base = "http://example.org/collections/"
terminology_graph = "http://example.org/terminologies/"

bartoc = read_json(f"{data}/bartoc-subset.json")

collection_1 = read_json(f"{data}/collections/1.json")
collection_1_full = {
    **collection_1,
    "partOf": [base]
}
collection_0 = {
    "name": "another test collection",
    "url": "https://example.com/",
}
collection_3_full = {
    **collection_0,
    "id": "3",
    "uri": f"{base}3",
    "partOf": [base]
}


def expect_error(client, method, path, json=None, error=None, code=400, **kwargs):
    res = client.open(path, method=method, json=json, **kwargs)
    assert res.status_code == code
    if error:
        if type(error) is str:
            error = {"message": error}
        error["code"] = code
        res = res.get_json()
        for key in error:
            assert res.get(key, None) == error[key]


def count_graphs(sparql):
    query = "SELECT ?g (count(*) as ?t) { GRAPH ?g {?s ?p ?o} } GROUP BY ?g"
    graphs = {}

    for row in sparql.query(query):
        if "g" in row:  # <https://github.com/RDFLib/rdflib/issues/3382>
            graphs[row['g']['value']] = int(row['t']['value'])
    return graphs


@pytest.fixture
def client(tmp_path):
    app.testing = True

    configure(title="Graph Import API TEST",
              stage=tmp_path, sparql=sparqlApi, data=data)

    store = app.config["store"]

    with app.test_client() as client:
        def fail(*args, **kwargs):
            return expect_error(client, *args, **kwargs)
        yield client, fail, tmp_path, store
        for g in store.count_graphs():  # flush triple store after each test
            store.drop_graph(g)


def mock_requests_get(url):
    uri = parse_qs(urlparse(url).query)['uri'][0]
    json = next(([item] for item in bartoc if item["uri"] == uri), [])
    return type('', (), {'json': lambda s: json})()


def test_validation(client):
    client, fail, _a, _b = client

    # malformed payload
    fail("PUT", "/collections/1", data="", error="The browser (or proxy) sent a request that this server could not understand.")
    fail("PUT", "/collections/1", [], "expected JSON object")
    fail("PUT", "/collections/1", {"uri": "http://example.org/collections/2"},
         "URI http://example.org/collections/2 and id 1 don't match")
    fail("PUT", "/collections/1", {"url": "http:/example.org/"}, {
        'message': "'http:/example.org/' does not match '^https?://'",
        'position': {'jsonpointer': '/url'}})
    fail("PUT", "/collections/1", {"id": "2"}, "ids 1 and 2 don't match")

    fail("PUT", "/collections/", {}, "expected list of collections")
    fail("PUT", "/collections/", [{"id": "1", "uri": "http://example.org/collections/2"}],
         "URI http://example.org/collections/2 and id 1 don't match")
    fail("POST", "/collections/",
         {"id": "1", "uri": "http://example.org/collections/2", "name": "x"},
         "URI http://example.org/collections/2 and id 1 don't match")
    fail("POST", "/collections/", {})


def test_general(client, monkeypatch):
    client, *_ = client

    res = client.get('/data/')
    assert res.status_code == 200
    assert res.json

    client.get('/data/skos.rdf').status_code == 200

    status = client.get('/status.json')
    assert status.status_code == 200
    assert status.json["title"] == "Graph Import API TEST"
    assert status.json["connected"] is True
    assert status.json["collections"] == 0

    metadata = client.get('/metadata')
    assert metadata.json == {
        "terminologies": [],
        "mappings": [],
        "collections": []
    }

    response = client.get("/openapi.json")
    schema = read_json(Path(__file__).parent / "openapi-schema.json")
    jsonschema.validate(response.get_json(), schema)


    # test backend failure
    monkeypatch.setattr(app.config["store"], "query", None)
    status = client.get('/status.json').json
    assert status["connected"] is False
    assert "collections" not in status


def test_terminology(client):
    client, fail, stage, sparql = client

    # get unregisterd terminology
    fail("GET", "/terminologies/18274", code=404)
    fail("GET", "/terminologies/18274/stage/", code=404)

    # register terminology from BARTOC
    with patch('requests.get', new=mock_requests_get):
        assert client.put("/terminologies/18274").status_code == 200
        assert client.get("/terminologies/18274").status_code == 200

        # try to register non-existing terminology
        fail("PUT", "/terminologies/0", code=404)

    # one terminology has been registered
    resp = client.get('/terminologies/')
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1

    status = client.get('/status.json')
    assert status.json["terminologies"] == 1

    assert sparql.count_graphs() == {
        'http://example.org/terminologies/': 13,
        'http://example.org/collections/': 1,
        'http://example.org/mappings/': 1
    }

    query = ("SELECT ?modified { GRAPH <http://example.org/terminologies/> {"
             "<http://example.org/terminologies/> <http://purl.org/dc/terms/modified> ?modified "
             "} }")
    modified = sparql.query(query)
    assert len(modified) == 1
    assert modified[0]["modified"]["datatype"] == "http://www.w3.org/2001/XMLSchema#dateTime"

    assert client.get("/terminologies/18274/stage/").status_code == 200

    # no data has been received yet
    fail("GET", "/terminologies/18274/stage/terminologies-18274.nt", code=404)

    # get list of terminology namespaces
    assert client.get("/terminologies/namespaces.json").get_json() == {
        "http://bartoc.org/en/node/18274": "http://www.w3.org/2004/02/skos/core#"}

    # replace list of terminologies
    fail("PUT", "/terminologies/", json={})
    fail("PUT", "/terminologies/", json=[{}], code=400)
    fail("PUT", "/terminologies/", json=[{"uri": "x"}], code=400)
    assert len(client.get('/terminologies/').get_json()) == 1
    assert client.put("/terminologies/", json=[]).status_code == 200
    assert client.get('/terminologies/').get_json() == []
    assert client.get("/terminologies/namespaces.json").get_json() == {}

    with patch('requests.get', new=mock_requests_get):
        json = [{"uri": "http://bartoc.org/en/node/18274"}]
        assert client.put("/terminologies/", json=json).status_code == 200
    assert len(client.get('/terminologies/').get_json()) == 1

    # receive terminology data and check log
    fail("GET", '/terminologies/18274/receive', code=404)
    fail("POST", '/terminologies/18274/receive', code=404)
    fail("POST", '/terminologies/18274/receive?from=abc', code=400)
    fail("POST", '/terminologies/18274/receive?from=abc.rdf', code=404)
    assert client.post(
        '/terminologies/18274/receive?from=skos.rdf').status_code == 200
    assert client.get('/terminologies/18274/receive').status_code == 200
    assert client.get("/terminologies/18274/stage/terminologies-18274.nt").status_code == 200

    # load terminology data and check log
    fail("GET", '/terminologies/18274/load', code=404)
    assert client.post('/terminologies/18274/load').status_code == 200
    assert client.get('/terminologies/18274/load').status_code == 200

    # no Skosmos configuraton as it's no SKOS vocabulary
    fail("GET", "/terminologies/18274/stage/skosmos.ttl", code=404)

    # try to receive and load an unregistered terminology
    fail("POST", '/terminologies/20533/receive?from=abc', code=404)
    fail("POST", '/terminologies/20533/load', code=404)

    # register, receive, and load another terminology
    with patch('requests.get', new=mock_requests_get):
        fail("PUT", '/terminologies/20533', code=200)
    fail("POST", '/terminologies/20533/load', code=404)
    assert client.post(
        '/terminologies/20533/receive?from=20533.concepts.ndjson').status_code == 200
    assert client.post('/terminologies/20533/load').status_code == 200

    # check Skosmos configuration
    skosmos = Path(f"{data}/skosmos-20533.ttl").read_text().rstrip()
    assert client.get("/terminologies/20533/stage/skosmos.ttl").data.decode("utf-8") == skosmos
    assert client.get("/terminologies/skosmos.ttl").data.decode("utf-8") == skosmos

    # check size of terminology graphs
    assert count_graphs(sparql) == {
        'http://example.org/terminologies/': 38,
        'http://example.org/collections/': 1,
        'http://example.org/mappings/': 1,
        'http://bartoc.org/en/node/18274': 377,
        'http://bartoc.org/en/node/20533': 679
    }
    assert client.post("/terminologies/20533/remove").status_code == 200
    assert count_graphs(sparql) == {
        'http://example.org/terminologies/': 37,
        'http://example.org/collections/': 1,
        'http://example.org/mappings/': 1,
        'http://bartoc.org/en/node/18274': 377
    }

    # no problem when graph has already been removed (but is registered still)
    assert client.post("/terminologies/20533/remove").status_code == 200

    # graph must be registered to be removed
    fail("POST", "/terminologies/1234/remove", code=404)

    # delete terminology
    assert client.delete('/terminologies/18274').status_code == 200
    assert count_graphs(sparql) == {
        'http://example.org/terminologies/': 36,
        'http://example.org/collections/': 1,
        'http://example.org/mappings/': 1
    }


def test_api(client):
    client, fail, stage, sparql = client

    # start without collections
    resp = client.get('/')
    assert resp.status_code == 200
    assert client.get('/grimpo-icon.png').status_code == 200

    assert client.get('/data/').status_code == 200
    assert client.get('/data/data.ttl').status_code == 200

    # collection endpoints
    assert client.get('/collections/schema.json').status_code == 200

    resp = client.get('/collections/')
    assert resp.status_code == 200
    assert resp.get_json() == []
    fail("GET", '/collections/1', code=404)

    # register collection
    assert client.put('/collections/', json=[collection_1]).status_code == 200

    resp = client.get('/collections/')
    assert resp.status_code == 200
    assert resp.get_json() == [collection_1_full]

    resp = client.get('/collections/1')
    assert resp.status_code == 200
    assert resp.get_json() == collection_1_full

    assert client.get("/collections/1/stage/").status_code == 200

    assert count_graphs(sparql) == {
        'http://example.org/collections/': 5,
        'http://example.org/terminologies/': 1,
        'http://example.org/mappings/': 1
    }

    # delete collection
    assert client.delete('/collections/1').status_code == 200
    fail("GET", '/collections/1', code=404)

    # try to receive and load non-existing collection
    fail("POST", '/collections/1/receive', code=404)
    fail("POST", '/collections/1/load', code=404)
    fail("POST", '/collections/1/add', code=404)

    # add again
    resp = client.put('/collections/1', json=collection_1)
    assert resp.status_code == 200  # TODO: should be 201 Created

    resp = client.get('/collections/1')
    assert resp.status_code == 200
    assert resp.get_json() == collection_1_full

    # add another collection with auto-id
    collection_autoid = {"name": "A", "url": "http://example.com/"}
    resp = client.post('/collections/', json=collection_autoid)
    assert resp.status_code == 200  # TODO: should be 201 Created
    assert resp.get_json() == {
        **collection_autoid, "id": "2",
        "uri": "http://example.org/collections/2",
        "partOf": ["http://example.org/collections/"]
    }

    # purge collections
    assert client.put('/collections/', json=[]).status_code == 200

    # add without id in record
    resp = client.put('/collections/3', json=collection_0)
    assert resp.status_code == 200  # TODO: should be 201 Created
    assert resp.get_json() == collection_3_full

    # add without known id
    resp = client.post('/collections/', json=collection_0)
    assert resp.status_code == 200  # TODO: should be 201 Created
    assert resp.get_json()["id"] == "4"

    # receive from file
    fail("POST", '/collections/3/receive', code=404)
    assert client.post(
        '/collections/3/receive?from=data.ttl').status_code == 200
    assert client.get('/collections/3/receive').status_code == 200

    # FIXME: this should not end up in loadable data!!!
    # fail('POST', '/collections/3/receive?from=namespace-prefix-undefined.ttl', error={
    #    "message": "The prefix skos: has not been declared",
    #    "position": {"line": 2, "linecol": "2:5"}
    # })

    # load received RDF
    assert client.post('/collections/3/load').status_code == 200
    assert client.get('/collections/3/load').status_code == 200

    uri = f"{base}3"
    query = f"SELECT * {{ GRAPH <{uri}> {{?s ?p ?o}} }} ORDER BY DESC(?s)"
    res = sparql.query(query)
    graph = [{'s': {'type': 'uri', 'value': 'https://example.org/x'},
              'p': {'type': 'uri', 'value': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'},
             'o': {'type': 'uri', 'value': 'http://www.cidoc-crm.org/cidoc-crm/E1_CRM_Entity'}},
             {'s': {'type': 'uri', 'value': 'http://www.cidoc-crm.org/cidoc-crm/E1_CRM_Entity'},
             'p': {'type': 'uri', 'value': 'https://example.org/foo'},
              'o': {'type': 'uri', 'value': 'https://example.org/bar'}}]
    assert res == graph

    # register terminology and receive + load again
    # test local BARTOC cache
    copy(f"{data}/bartoc-crm.json", f"{data}/bartoc.json")
    fail("PUT", '/terminologies/18274', code=404)
    assert client.put('/terminologies/1644').status_code == 200  # CIDOC-CRM
    os.remove(f"{data}/bartoc.json")

    client.post('/collections/3/receive?from=data.ttl')
    client.post('/collections/3/load')
    assert sparql.query(query) == graph[:1]

    assert client.post('/collections/3/receive?from=rdf.zip').status_code == 200
    assert client.post('/collections/3/load').status_code == 200

    query = f"SELECT ?e {{ GRAPH <{base}3> {{ ?e a ?t }} }} ORDER BY ?o"
    res = [r["e"]["value"] for r in sparql.query(query)]
    assert res == [f'https://example.org/e{i}' for i in [1, 2, 3, 4]]

    assert client.post(
        '/terminologies/1644/receive?from=crm.ttl').status_code == 200

    # TODO: test file upload
    # with open(f"{data}/data.ttl", "rb") as f:
    #    data = {"data.ttl":f}
    #    res = client.post('/collections/1/receive', data=data,
    #                  content_type='multipart/form-data')
    #    assert res.status_code == 200

    # assert client.post('/collections/1/load').status_code == 404
    query = f"SELECT * {{ GRAPH <{base}> {{ <{base}3> <http://purl.org/dc/terms/issued> ?d}} }}"
    assert len(sparql.query(query)) == 1

    # remove graph, keep registered
    assert client.post('/collections/3/remove').status_code == 200
    assert client.get('/collections/3').status_code == 200
    assert len(sparql.query(query)) == 0

    # cannot receive directory
    assert client.post('/collections/3/receive?from=collection').status_code == 400


def test_mappings(client):
    client, fail, stage, sparql = client

    assert client.post('/mappings/', json={}).status_code == 200
    assert client.get('/mappings/1').status_code == 200

    assert client.put('/mappings/', json=[{"name": "A"}, {"name": "B"}]).status_code == 200
    assert client.get('/mappings/1').status_code == 200
    assert client.get('/mappings/2').status_code == 200

    # receive and load JSKOS mappings as NDJSON
    assert client.post('/mappings/1/receive?from=mappings.ndjson').status_code == 200
    assert client.post('/mappings/1/load').status_code == 200
    assert list(client.get('/mappings/1/receive').get_json().values()) == [
        'Receiving 1 from mappings.ndjson',
        f'Retrieving source {data}/mappings.ndjson from data directory',
        'Converting JSKOS mappings to RDF mapping triples',
        'Processed 1 mappings',
        f'Extracting RDF from file://{stage}/mappings/1/original.ttl as Turtle',
        'Removed 0 triples, changed 0 triples, kept 1 triples.',
        'done']

    query = "SELECT ?x { <http://example.org/A> ?p ?x }"
    assert sparql.query(query) == [{'x': {'type': 'uri', 'value': 'http://example.com/A'}}]

    # detach mappings
    mappings = [{"type": ["http://www.w3.org/2004/02/skos/core#exactMatch"], "from": {"memberSet": [
        {"uri": "http://example.org/A"}]}, "to": {"memberSet": [{"uri": "http://example.com/A"}]}}]
    assert client.post('/mappings/1/detach', json=mappings).status_code == 200
    assert sparql.query(query) == []

    # TODO: append mappings

    # receive ad load JSKOS mappings as JSON (array)
    assert client.post('/mappings/1/receive?from=mappings2.json').status_code == 200
    assert client.post('/mappings/1/load').status_code == 200
    assert sparql.query(query) == [{'x': {'type': 'uri', 'value': 'http://example.com/foo'}}]

    # receive ad load JSKOS mappings as JSON (object)
    assert client.post('/mappings/1/receive?from=mappings3.json').status_code == 200
    assert client.post('/mappings/1/load').status_code == 200
    assert sparql.query(query) == [{'x': {'type': 'uri', 'value': 'http://example.com/bar'}}]

    assert client.post('/mappings/1/receive?from=invalid-mappings.json').status_code == 400

    # receive and load RDF mappings
    assert client.post('/mappings/2/receive?from=mappings.ttl').status_code == 200
    assert client.post('/mappings/2/load').status_code == 200

    query = "SELECT ?x { <http://d-nb.info/gnd/4193078-2> ?p ?x }"
    assert len(sparql.query(query)) == 1

    assert client.get("/mappings/2/stage/").status_code == 200
