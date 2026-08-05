# Unit test
from lib import CollectionRegistry
from .utils import config  # noqa: F401


def test_collections(config):
    CollectionRegistry(**config)
    # TODO
