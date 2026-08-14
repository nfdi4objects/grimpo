import pytest
from .utils import config  # noqa: F401
from lib import (
    TerminologyRegistry,
    ValidationError,
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
        }],
        # these should be ignored:
        "concepts": [{"uri": "http://example.org/1"}],
        "creator": [{"uri": "http://example.org/2"}],
        "contributor": [{"uri": "http://example.org/3"}],
    }


def test_nested_contexts(config, monkeypatch):
    # The conversion must not make HTTP requests.
    def fail_network(*_args, **_kwargs):
        raise AssertionError("Unexpected HTTP request")  # pragma: no cover

    monkeypatch.setattr("requests.get", fail_network)

    bartoc = config["data"] / "bartoc.json"
    write_json(bartoc, [terminology(1578)])

    store = config["store"]
    registry = TerminologyRegistry(**config)

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
    assert len(store.query(query)) == 9

    # Try to add a terminology with unsupported JSKOS context URL
    write_json(bartoc, [terminology(1579, "https://example.org/context.json")])
    with pytest.raises(ValidationError, match="Unsupported remote"):
        registry.replace([{"uri": "http://bartoc.org/en/node/1579"}])

    # leaves the registry and graph unchanged
    assert [item["id"] for item in registry.list()] == ["1578"]
    assert len(store.query(query)) == 9
