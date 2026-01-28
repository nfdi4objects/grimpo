# Unit test
from lib import triple_iterator, RDFFilter, ValidationError


def parse(source, filter=None, unique=False):
    triples = [(s, p, o) for s, p, o in triple_iterator(source)]
    if filter:
        triples = [t for t in [filter.check_triple(*t) for t in triples] if type(t) is list]
    if unique:
        triples = [list(t) for t in set(tuple(t) for t in triples)]
    return triples


def fail(file, error):
    try:
        parse(file)
        assert file == f"parsing {file} should have thrown ValidationError!"
    except ValidationError as e:
        assert e.to_dict() == error


def test_parsing():
    assert len(parse("tests/skos.rdf")) == 377
    assert len(parse("tests/rdf.zip")) == 4
    assert len(parse("tests/iri.ttl")) == 1

    fail("tests/invalid.nt", {"message": "<http://example.org/?q=a|b> is no valid IRI"})

    fail("tests/namespace-prefix-undefined.ttl", {
        "message": "The prefix skos: has not been declared",
        "position": {"line": 2, "linecol": "2:5"}
    })

    fail("tests/missing-namespace.xml", {
        "message": "XML namespaces are required in RDF/XML"
    })

    fail("tests/not-wellformed.xml", {
        "message": "syntax error: tag not closed: `>` not found before end of input"
    })

    fail("tests/nested-error.zip", {
        "message": "The prefix skos: has not been declared in syntax.ttl in syntax.ttl.zip",
        "position": [{
            "address": "syntax.ttl.zip",
            "dimension": "file",
            "errors": [{
                "message": "The prefix skos: has not been declared in syntax.ttl",
                "position": [{
                    "address": "syntax.ttl",
                    "dimension": "file",
                    "errors": [{
                        "message": "The prefix skos: has not been declared",
                        "position": {
                            "line": 2,
                            "linecol": "2:5",
                        }
                    }]
                }]
            }]
        }]
    })


def test_filter():
    triples = parse("tests/filter.ttl")
    assert len(triples) == 7

    filter = RDFFilter(disallow_subject_ns=("http://www.cidoc-crm.org/cidoc-crm/"))
    triples = parse("tests/filter.ttl", filter, True)
    assert len(triples) == 3
