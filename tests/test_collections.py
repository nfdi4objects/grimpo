# Unit test
import pytest
import tempfile
from lib import CollectionRegistry, createTripleStore


@pytest.fixture
def config():
    with tempfile.TemporaryDirectory() as tempdir:
        yield {
            "base": "http://example.org/",
            "stage": f"{tempdir}/stage",
            "data": f"{tempdir}/data",
        }


def test_collections(config):
    # print(config)
    config["store"] = createTripleStore(False)  # in-memory
    CollectionRegistry(**config)
    # TODO
