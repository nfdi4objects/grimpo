from lib.formats import guess_format


def test_formats():
    file = __file__  # .py
    assert guess_format(file, None) is None
    assert guess_format(file, "xy") is None
    assert guess_format(file, "nt") == "nt"
    assert guess_format(file, "https://format.gbv.de/rdf/turtle") == "ttl"

    assert guess_format("x.ndjson") == "ndjson"
