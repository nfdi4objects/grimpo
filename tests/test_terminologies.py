import pytest

from lib import (
    TerminologyRegistry,
    ValidationError,
    createTripleStore,
    write_json,
)


JSKOS_CONTEXT_URL = "https://gbv.github.io/jskos/context.json"


def terminology(terminology_id, nested_context=JSKOS_CONTEXT_URL):
    """Create a minimal terminology with a nested JSON-LD context."""
    return {
        "@context": JSKOS_CONTEXT_URL,
        "uri": f"http://bartoc.org/en/node/{terminology_id}",
        "subject": [{
            "@context": nested_context,
            "uri": "http://dewey.info/class/3/e23/",
            "notation": ["3"],
        }],
        "media": [{
            "type": "Manifest",
            "items": [],
            "thumbnail": [{
                "type": "Image",
                "id": "http://example.org/1/thumbnail.jpg",
                "format": "image/jpeg"
            }]
        }]
    }


def test_nested_contexts(tmp_path, monkeypatch):
    # The conversion must not make HTTP requests.
    def fail_network(*_args, **_kwargs):
        raise AssertionError(
            "JSON-LD context unexpectedly fetched over the network")

    monkeypatch.setattr("requests.get", fail_network)

    data = tmp_path / "data"
    data.mkdir()
    dump = data / "bartoc.json"
    write_json(dump, [terminology(1578)])

    store = createTripleStore()
    registry = TerminologyRegistry(
        base="http://example.org/",
        data=data,
        stage=tmp_path / "stage",
        store=store,
    )

    # A different fallback proves that the declared context is preserved.
    registry.context = {
        "uri": "@id",
        "subject": "http://example.org/fallback-subject",
    }

    # The known JSKOS context is loaded from the bundled local copy.
    registry.replace([{"uri": "http://bartoc.org/en/node/1578"}])
    assert [item["id"] for item in registry.list()] == ["1578"]

    # The metadata graph proves that "subject" was mapped by the JSKOS context.
    graph = "http://example.org/terminology/"
    query = (
        f"SELECT * {{ GRAPH <{graph}> "
        "{ ?s <http://purl.org/dc/terms/subject> ?o } }"
    )
    assert len(store.query(query)) == 1

    # Expected number of triples
    query = f"SELECT * {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
    assert len(store.query(query)) == 8

    # Try to add a terminology with unsupported JSKOS context URL
    write_json(dump, [terminology(1579, "https://example.org/context.json")])
    with pytest.raises(ValidationError, match="Unsupported remote"):
        registry.replace([{"uri": "http://bartoc.org/en/node/1579"}])

    # leaves the registry and graph unchanged
    assert [item["id"] for item in registry.list()] == ["1578"]
    assert len(store.query(query)) == 8
