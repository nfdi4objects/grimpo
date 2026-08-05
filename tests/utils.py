import pytest
from lib import createTripleStore


@pytest.fixture
def config(tmp_path):
    stage = tmp_path / "stage"
    data = tmp_path / "data"
    data.mkdir()

    return dict(
        base="http://example.org/",
        stage=stage,
        data=data,
        store=createTripleStore(False)
    )
