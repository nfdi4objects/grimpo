# grimpo

[![Docker image](https://github.com/nfdi4objects/n4o-graph-importer/actions/workflows/docker.yml/badge.svg)](https://github.com/orgs/nfdi4objects/packages/container/package/n4o-graph-importer)
[![Test](https://github.com/nfdi4objects/n4o-graph-importer/actions/workflows/test.yml/badge.svg)](https://github.com/nfdi4objects/n4o-graph-importer/actions/workflows/test.yml)

> Import RDF data into a Knowledge Graph

This knowledge graph importer named **grimpo** provides a [web service](#api) for controlled import of RDF data into the triple store of a knowledge graph. The knowledge graph is [split into](#graph) indivual data collections, terminologies, and mappings.

Grimpo is provided [as Docker image](https://github.com/nfdi4objects/n4o-graph-importer) but it can also be run from sources for [development and testing](#development).

Development is being funded as part of [NFDI4Objects](https://www.nfdi4objects.net/) to build the [NFDI4Objects Knowledge Graph](https://graph.nfdi4objects.net/). 

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Data sources](#data-sources)
  - [Graphs](#graphs)
  - [Validation](#validation)
  - [Filtering](#filtering)
  - [Reports](#reports)
- [API](#api)
  - [General endpoints](#general-endpoints)
    - [GET /status.json](#get-statusjson)
    - [GET /data/](#get-data)
  - [Terminologies](#terminologies)
    - [GET /terminology](#get-terminology)
    - [GET /terminology/{id}](#get-terminologyid)
    - [PUT /terminology/{id}](#put-terminologyid)
    - [DELETE /terminology/{id}](#delete-terminologyid)
    - [PUT /terminology/](#put-terminology)
    - [GET /terminology/{id}/stage/](#get-terminologyidstage)
    - [POST /terminology/{id}/receive](#post-terminologyidreceive)
    - [GET /terminology/{id}/receive](#get-terminologyidreceive)
    - [POST /terminology/{id}/load](#post-terminologyidload)
    - [GET /terminology/{id}/load](#get-terminologyidload)
    - [POST /terminology/{id}/remove](#post-terminologyidremove)
    - [GET /terminology/namespaces.json](#get-terminologynamespacesjson)
    - [GET /terminology/skosmos.ttl](#get-terminologyskosmosttl)
  - [Collections](#collections)
    - [GET /collection/](#get-collection)
    - [GET /collection/schema.json](#get-collectionschemajson)
    - [PUT /collection/](#put-collection)
    - [POST /collection/](#post-collection)
    - [GET /collection/{id}](#get-collectionid)
    - [PUT /collection/{id}](#put-collectionid)
    - [DELETE /collection/{id}](#delete-collectionid)
    - [GET /collection/{id}/stage/](#get-collectionidstage)
    - [POST /collection/{id}/receive](#post-collectionidreceive)
    - [GET /collection/{id}/receive](#get-collectionidreceive)
    - [POST /collection/{id}/load](#post-collectionidload)
    - [GET /collection/{id}/load](#get-collectionidload)
    - [POST /collection/{id}/remove](#post-collectionidremove)
  - [Mappings](#mappings)
    - [GET /mappings/](#get-mappings)
    - [GET /mappings/schema.json](#get-mappingsschemajson)
    - [GET /mappings/properties.json](#get-mappingspropertiesjson)
    - [PUT /mappings/](#put-mappings)
    - [POST /mappings/](#post-mappings)
    - [GET /mappings/{id}](#get-mappingsid)
    - [PUT /mappings/{id}](#put-mappingsid)
    - [DELETE /mappings/{id}](#delete-mappingsid)
    - [POST /mappings/{id}/append](#post-mappingsidappend)
    - [POST /mappings/{id}/detach](#post-mappingsiddetach)
    - [GET /mappings/{id}/stage/](#get-mappingsidstage)
    - [POST /mappings/{id}/receive](#post-mappingsidreceive)
    - [GET /mappings/{id}/receive](#get-mappingsidreceive)
    - [POST /mappings/{id}/load](#post-mappingsidload)
    - [GET /mappings/{id}/load](#get-mappingsidload)
    - [POST /mappings/{id}/remove](#post-mappingsidremove)
- [Development](#development)
- [License](#license)

## Installation

The application does not include any methods of authentification. It is meant to be deployed together with components described in [n4o-graph](https://github.com/nfdi4objects/n4o-graph) repository. In particular:

- [n4o-fuseki](https://github.com/nfdi4objects/n4o-fuseki): RDF triple store
- [n4o-graph-apis](https://github.com/nfdi4objects/n4o-graph-apis): web interface and public SPARQL endpoint

## Configuration

The web service and its Docker image can be configured via environment variables:

- `TITLE`: title of the application. Default: `Knowledge Graph Importer`
- `BASE`: base URI of named graphs. Default: `http://example.org/`
- `SPARQL`: API endpoint of SPARQL Query protocol, SPARQL Update protocol and SPARQL Graph store protocol. An in-memory Triple store is used as fallback if `SPARQL` is not set.
- `STAGE`: writeable stage directory. Default: `stage`
- `DATA`: local data directory for file import
- `FRONTEND`: URL of [n4o-graph-apis] instance. This is included as field `frontend` in [/status.json](#get-statusjson) and shown in the HTML interface for convenience. Default is the value of `BASE`

## Usage

Three kinds of data can be imported seperately:

- **terminologies** such as ontologies and controlled vocabularies (as listed in [BARTOC])
- **collections** of arbitrary RDF data from open research data repositories
- **mappings** between resources from terminologies

Each terminology, each collection, and each mapping source is imported into an individual named [graph]. 

Importing is controlled via [an HTTP API](#api) in three steps:

1. **register**: metadata is retrieved, collected in a **registry** and written to the triple store
2. **receive**: data is retrieved into a **stage** directory where it is [validated](#validation), [filtered](#filtering), and a [report] is generated
2. **load**: processed data is loaded into the **triple store**

Register can be undone by additional step **delete**. Load and receive can be undone by step **remove**. Mappings can also be injested and withdraw directly into/from the triple store via **append/detach** to support non-durable live-updates. Register and load also log information into [reports](#reports).

```mermaid
flowchart LR
  END[ ]:::hidden
  START[ ]:::hidden
  C[ ]:::hidden
  R["<b>registry</b>"]
  S("<b>stage</b>"):::data
  T("<b>triple store</b>"):::data

  START -- register --> R
  R -- receive --> S
  S -- load --> T
  T -- remove --> R
  R -- delete --> END
  END ~~~ R
  C  ~~~ R
  C <-. append/detach .-> T

classDef hidden display: none;
classDef data stroke:#4d8dd1, fill:#D4E6F9;
```

### Data sources

Metadata of **[collections](#collections)** and **[mapping sources]** must be provided in a custom JSON format. Example:

~~~json
{
  "name": "African Red Slip Ware",
  "license": "http://creativecommons.org/licenses/by/4.0/",
  "url": "https://doi.org/10.5281/zenodo.5642751",
  "distributions": [
    {
      "url": "https://doi.org/10.5281/zenodo.5642751"
    }
  ]
}
~~~

**[Terminology](#terminologies)** metadata is taken from [BARTOC] via its public API when registering a terminology (with [PUT /terminology/{id}](#put-terminologyid) or [PUT /terminology/](#put-terminology)). If the data directory contains a file `bartoc.json` with an array of JSKOS records from BARTOC, this file is used as source of terminology metadata instead. Script `update-terminologies` in this repository can be used to get a subset from BARTOC, including all [terminologies listed in NFDI4Objects](https://bartoc.org/vocabularies?partOf=http://bartoc.org/en/node/18961).

The location of data is taken from metadata field `distributions`. The first array field having either subfield `download` (with direct download URL) or subfield `url` (with Zenodo DOI) is used. Subfield `format` can be added to specificy the data format. The following formats are supported:

- RDF/XML: `xml` or `https://format.gbv.de/rdf/xml`)
- Turtle: `ttl` or `https://format.gbv.de/rdf/turtle`)
- N-Triples: `nt` or `https://format.gbv.de/rdf/ntriples`)
- Newline delimited JSON: `ndjson` or `https://format.gbv.de/ndjson`) with JSKOS records (only for terminologies and mappings)
- ZIP Archive with RDF Files (`*.{nt,ttl,rdf,xml}`): `zip` or `https://format.gbv.de/zip`. The archive is extracted recursively on receive.

Format of Zenodo DOI data is always `zip`.

The location can be overridden on receive with optional query parameter `from` pointing to an URL or a file name from [local data directory.](#configuration). These locations are not made public.


### Graphs

[graph]: #graphs

The knowledge graph is organized in individual named graphs. URIs of most of these graphs are based on a namespace prefix, like `http://example.org/`. The prefix base should be changed by [configuration](#configuration) first.

- metadata about all terminologies is in graph of URI `http://example.org/terminology/`

- metadata about all collections is in graph of URI `http://example.org/collection/`

- metadata about all mapping sources is in graph of URI `http://example.org/mappings/`

- each terminology is imported into a graph by its [BARTOC] URI

- each collection is imported into a graph of URI namespace `http://example.org/collection/`, followed by a numeric identifier

- mappings are grouped into mapping sources, each imported into a graph of URI namespace `http://example.org/mappings/`, followed by a numeric identifier

```mermaid
flowchart TD
    collectionMeta --describe--> collection
    terminologyMeta -- describe --> terminology
    mappingsMeta --describe--> mappings    

    collectionMeta["collection/"]
    collection["collection/{id}"]
    terminology["terminology/{id}"]
    terminologyMeta["terminology/"]
    mappings["mappings/{id}"]
    mappingsMeta["mappings/"]
```

### Validation

Received data in RDF or JSKOS format must be syntactically valid. Additional constraints are being implemented. Validation errors are returned in [Data Validation Error Format]. For instance an error like this is emitted when JSON field `url` is no valid URL:

~~~json
{
  "message": "'http:/example.org/' does not match '^https?://'",
  "position" {
    "jsonpointer": "/url"
  }
}
~~~

**JSON metadata** to describe collections and mapping sources is validated with JSON Schemas [collection-schema.json] and [mappings-schema.json], respectively.

**JSKOS data** (for terminologies and mappings) is not validated yet (see [open issue](https://github.com/nfdi4objects/n4o-graph-importer/issues/50)).

JSON-LD context SHOULD be <https://gbv.github.io/jskos/context.json>. It is not retrieved from the network but loaded from a local copy where field `concepts` has been removed to limit JSKOS data to terminology metadata. Support of images ([`media`](https://gbv.github.io/jskos/#media))
is limited to thumbnails with `id` (image URL) and `format`.

Other remote context URLs are rejected. Other embedded context declarations are preserved but this may be removed in a future version.

**RDF data** is allowed to contain any absolute IRI references matching the regular expression `` ^[a-z][a-z0-9+.-]*:[^<>"{}|^`\\\x00-\x20]*$ ``. This includes some IRI references invalid in theory but  supported by most RDF software in practice. Additional constraints on RDF data do not result in validation errors but malformed triples are filtered out (as described in the following) and collected as part of [report] files.

### Filtering

[filtering]: #filtering

RDF data is filtered depending on kind of data and configuration. Triples (aka RDF statements) matching the following criteria are filtered out:

- Triples with relative IRI references and local `file:` URIs

- Statements about registered terminologies in collection data

- ... *(RDF filtering is still being worked on and not fully documented yet)*

Filtered RDF triples are collected as part of reports.

### Reports

[report]: #reports

Reports are generated on receiving and loading data. The final format of reports has not been specified yet.

Reports can be accessed with the following API methods:

- [GET /terminology/{id}/receive](#get-terminologyidreceive)
- [GET /terminology/{id}/load](#get-terminologyidload)
- [GET /collection/{id}/receive](#get-collectionidreceive)
- [GET /collection/{id}/load](#get-collectionidload)
- [GET /mappings/{id}/receive](#get-mappingsidreceive)
- [GET /mappings/{id}/load](#get-mappingsidload)

Receiving data generates two additional files in the stage directory (replace `{id}` with a selected numeric identifier):

- `terminology-{id}.nt`/`collection-{id}.nt`/`mappings-{id}.nt`: validated and filtered RDF triples to be imported
- `terminology-{id}-removed.nt`/`collection-{id}-removed.nt`/`mappings-{id}-removed.nt`: triples removed on [filtering]

## API

There is a minimal HTML interface at root path (**GET /**) to try out the API. This is more useful than an interface generated automatically, for instance with Swagger. The API is not meant to be publically available (there is no authentification), so there is no need for an [OpenAPI](https://swagger.io/specification/) document anyway.

A HTTP 400 error with response body in [Data Validation Error Format] is returned if collection metadata or mapping source metadata does not conform to its corresponding JSON Schema.

### General endpoints

#### GET /status.json

Get curent information about the application as JSON object. This includes the [configuration](#configuration) with lowercase field names and field `connected` whether the SPARQL API endpoint can be accessed.

#### GET /data/

List and get files from local data directory.

### Terminologies

Terminologies are identified by their [BARTOC] identifier. Terminology data should be registered before receiving collection data to detect use of terminologies in collections.

#### GET /terminology

Return the list of registered terminologies.

#### GET /terminology/{id}

Return metadata of a registered terminology.

#### PUT /terminology/{id}

Register a terminology or update its metadata from BARTOC. The metadata is directly added to the triple store. Updates may lead to errors in description of terminologies because removal of statements is limited to simple triples with terminology URI as subject!

#### DELETE /terminology/{id}

Unregister a terminology and remove it from stage directory and triple store. This implies [DELETE /terminology/{id}/remove](#delete-terminologyidremove).

#### PUT /terminology/

Replace the list of terminologies. By unregistering all and registering a new list. The response body is expected to be a JSON array with objects having key `uri` with the BARTOC URI like this:

~~~json
[
 { "uri": "http://bartoc.org/en/node/18274" },
 { "uri": "http://bartoc.org/en/node/20533" }
]
~~~

Other fields are ignored so the return value of [GET /terminology/](#get-terminology) can be used as payload.

#### GET /terminology/{id}/stage/

List and get files of the stage directory of a terminology.

#### POST /terminology/{id}/receive

Receive terminology data. Data source is given in terminology metadata field `distributions` or via query parameter `from` (see [data sources](#data-sources)).

File format can be:

- RDF/Turtle for file extension `.ttl` or `.nt`
- RDF/XML for file extension `.rdf` or `.xml`
- JSKOS as newline delimited JSON for file extension `.ndjson`
- A ZIP archive containing RDF files for file extension `.zip`

#### GET /terminology/{id}/receive

Get latest receive [report] of a terminology.

#### POST /terminology/{id}/load

Load received terminology data into the triple store. If the terminology is SKOS format (possibly converted from JSKOS) and the terminology has title and language information, a configuration file `skosmos.ttl` to be used for [Skosmos](https://skosmos.org/) is also generated in the stage are of the terminology.

#### GET /terminology/{id}/load

Get latest load [report] of a terminology.

#### POST /terminology/{id}/remove

Remove terminology data from the triple store and from staging area. The terminology will still be registered and its metadata is not removed from the triple store.

#### GET /terminology/namespaces.json

Return registered URI namespaces forbidden to be used in RDF subjects. The result is a JSON object with terminology URIs as keys and namespaces as values. For instance the SKOS (<http://bartoc.org/en/node/18274>) namespace is <http://www.w3.org/2004/02/skos/core#> so RDF triples with subjects in this namespace can only be added to the knowledge graph via `/terminology/18274`.

#### GET /terminology/skosmos.ttl

Return Skosmos vocabulary configuration for imported (J)SKOS vocabularies.

### Collections

Collections are described in a custom JSON format described by JSON Schema [collection-schema.json]. This JSON data is enriched with field `id` and internally converted to RDF for import into the knowledge graph. In its simplest form, a collection should contain a name, an URL, and a license:

~~~json
{
  "name": "test collection",
  "url": "https://example.org/",
  "license": "https://creativecommons.org/publicdomain/zero/1.0/"
}
~~~

When registered, the collection is assigned an id, and a corresponding URI.

#### GET /collection/

Return the list of registered collections (metadata only).

#### GET /collection/schema.json

[collection-schema.json]: lib/collection-schema.json

Return the JSON Schema used to validation collection metadata. See file [collection-schema.json]. Collection field `id` is required by the schema but it gets assigned automatically in most cases.

#### PUT /collection/

Replace the list of collections by unregistering all and registering a new list of collections.

#### POST /collection/

Register a new collection or update metadata of a registered collection.

#### GET /collection/{id}

Return metadata of a specific registered collection.

#### PUT /collection/{id}

Update metadata of a specific registered collection or register a new collection.

#### DELETE /collection/{id}

Unregister a collection and remove it from the triple store and staging area. This implies [DELETE /collection/{id}/remove](#delete-collectionidremove).

#### GET /collection/{id}/stage/

List and get files of the stage directory of a collection.

#### POST /collection/{id}/receive

Receive and process collection data. Data source is given in collection metadata field `distributions` or via query parameter `from` (see [data sources](#data-sources)).

File format can be:

- RDF/Turtle for file extension `.ttl` or `.nt`
- RDF/XML for file extension `.rdf` or `.xml`
- A ZIP archive containing RDF files for file extension `.zip`

#### GET /collection/{id}/receive

Get latest receive [report] of a collection.

#### POST /collection/{id}/load

Load received and processed collection data into the triple store.

#### GET /collection/{id}/load

Get latest load [report] of a collection.

#### POST /collection/{id}/remove

Remove collection data from the triple store and from staging area. The collection will still be registered and its metadata is not removed from the triple store.

### Mappings

Mappings are grouped in **mapping sources**, which correspond to concordances or lists of mappings.

#### GET /mappings/

Return the list of registered mapping sources.

#### GET /mappings/schema.json

[mappings-schema.json]: lib/mappings-schema.json

Return the mapping sources schema [mappings-schema.json] used to validate mapping sources.

#### GET /mappings/properties.json

Get a list of supported mapping properties. By default this is the list of [SKOS Mapping properties](https://www.w3.org/TR/skos-reference/#mapping) plus `owl:sameAs`, `owl:equivalentClass`, `owl:equivalentProperty`, `rdfs:subClassOf`, and `rdfs:subPropertyOf`.

#### PUT /mappings/

Register a list of mapping sources. All existing mapping sources and mappings will be deleted.

#### POST /mappings/

Register a new mapping source or update metadata of a mapping source.

#### GET /mappings/{id}

Return a specific mapping source.

#### PUT /mappings/{id}

Update metadata of a specific mapping source.

#### DELETE /mappings/{id}

Unregister a mapping source and remove it from the triple store and staging area. This implies [DELETE /mappings/{id}/remove](#delete-mappingsidremove).

#### POST /mappings/{id}/append

Directly add mappings to the triple store, bypassing the receive/load workflow. Directly added triples are not stored in the staging area so they will not persist a load operation of the selected mapping source. Expects a JSON array with mappings in JSKOS format.

#### POST /mappings/{id}/detach

Directly remove mappings from the triple store. This operation is not reflected in the staging area so it will not persist a load operation of the seleceted mapping source. Expects a JSON array with mappings in JSKOS format. Non-existing mappings are ignored.

#### GET /mappings/{id}/stage/

List and get files of the stage directory of a mapping source.

#### POST /mappings/{id}/receive

Receive and process mappings from a mapping source. Data source is given in mapping source metadata field `distributions` or via query parameter `from` (see [data sources](#data-sources)).

Mappings can be given as:

- plain RDF triples in Turtle syntax (extension `.nt` or `.ttl`)
- plain RDF triples in RDF/XML syntax (extension `.rdf` or `.xml`)
- newline delimited JSON with [JSKOS Concept Mappings](https://gbv.github.io/jskos/#concept-mappings) (extension `.ndjson`). Only 1-to-1 mappings are included

Mapping metadata such as date of creation and annotations are ignored.

#### GET /mappings/{id}/receive

Get latest receive [report] of a mapping source.

#### POST /mappings/{id}/load

Load received and processed mapping into the triple store.

#### GET /mappings/{id}/load

Get latest load [report] of a mapping source.

#### POST /mappings/{id}/remove

Remove mappings of a specific mapping source from the triple store and from staging area. The mapping source will still be registered and its metadata is not removed from the triple store.

## Development

Requires basic development toolchain (`sudo apt install build-essential`) and Python 3 with module venv to be installed.

- `make deps` installs Python dependencies in a virtual environment in directory `.venv`
- `make test` runs a test instance of the service with a temporary triple store
- `make start` runs the service without restarting
- `make api` runs the service with automatic restarting (requires install Node module `nodemon` with `npm install`)
- `make lint` checks coding style
- `make fix` cleans up some coding style violations

Best use the Docker image [n4o-fuseki] to start a triple store configured to be used with the importer:

~~~sh
docker run --rm -p 3030:3030 ghcr.io/nfdi4objects/n4o-fuseki:main
~~~

To also inspect the content of the triple store, use [n4o-graph-apis].

*TODO: add description how to run this both*

The Docker image of grimpo is automatically build on GitHub. To locally build and run the image for testing:

~~~sh
docker image build -t grimpo .
IMPORTER_IMAGE=grimpo docker compose run --rm -p 5020:5020 importer
~~~

*TODO: add description how to also run triple store and apis*

## License

Licensed under [Apache License](http://www.apache.org/licenses/) 2.0.

[BARTOC]: https://bartoc.org/
[n4o-fuseki]: https://github.com/nfdi4objects/n4o-fuseki#readme
[n4o-graph-apis]: https://github.com/nfdi4objects/n4o-graph-apis#readme
[Data Validation Error Format]: https://gbv.github.io/validation-error-format/
