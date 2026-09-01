# Unit test
from pytest import raises
from pathlib import Path
from lib import CollectionRegistry
from .utils import config  # noqa: F401


requests = {
    "https://zenodo.org/api/records/13832255/files-archive": "rdf.zip",
    "http://example.com/data": "data.ttl"
}


def mock_urlopen(url):
    return (Path(__file__).parent / "data" / requests[url]).open("rb")


def test_distributions(config, monkeypatch):
    registry = CollectionRegistry(**config)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    id = "1"

    def register_with_url(url):
        registry.register(dict(id=id, name="hello",
                               url="http://example.com", distributions=[{}, {"url": url}]))

    register_with_url("http://example.org/")
    with raises(Exception):
        registry.receive(id)

    register_with_url("https://doi.org/10.5281/zenodo.13832255")
    registry.receive(id)
    assert "done" in registry.receive_log(id).values()


def test_collections(config, monkeypatch):
    registry = CollectionRegistry(**config)

    download = "http://example.com/data"
    id = "7"
    base = config["base"]

    col = dict(id=id, name="hello", url="http://example.com",
               distributions=[{"download": download}])
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    # 1. register
    res = registry.register(col)
    col['partOf'] = [f'{base}collection/']
    col['uri'] = f'{base}collection/{id}'

    assert res == col
    assert registry.get(id) == col

    # 2. receive
    with raises(Exception, match="Unknown data format"):
        res = registry.receive(id)

    registry.receive(id, format="ttl")
    assert "done" in registry.receive_log(id).values()

    # 3. load
    registry.load(id)
    # TODO: check result log
    # res = registry.sparql.query('SELECT * { ?s ?p ?o }')
