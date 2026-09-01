# Unit test
from lib import triple_iterator, RDFFilter, ValidationError


def parse(file, filter=None, unique=False):
    triples = [(s, p, o) for s, p, o in triple_iterator(f"tests/data/{file}")]
    if filter:
        triples = [t for t in [filter.check_triple(*t) for t in triples] if type(t) is list]
    if unique:
        triples = [list(t) for t in set(tuple(t) for t in triples)]
    return triples


def fail(file, error):
    try:
        parse(file)
        assert file == f"parsing {file} should have thrown ValidationError!"  # pragma: no cover
    except ValidationError as e:
        assert e.to_dict() == error


def test_parsing():
    assert len(parse("skos.rdf")) == 377
    assert len(parse("rdf.zip")) == 4
    assert len(parse("iri.ttl")) == 1

    fail("invalid.nt", {"message": "<http://example.org/?q=a|b> is no valid IRI"})

    fail("namespace-prefix-undefined.ttl", {
        "message": "The prefix skos: has not been declared",
        "position": {"line": 2, "linecol": "2:5"}
    })

    fail("missing-namespace.xml", {
        "message": "XML namespaces are required in RDF/XML"
    })

    fail("not-wellformed.xml", {
        "message": "syntax error: tag not closed: `>` not found before end of input"
    })

    fail("nested-error.zip", {
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
    triples = parse("filter.ttl")
    assert len(triples) == 7

    filter = RDFFilter(disallow_subject_ns=("http://www.cidoc-crm.org/cidoc-crm/"))
    triples = parse("filter.ttl", filter, True)
    assert len(triples) == 3
