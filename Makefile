deps:
	[ -d .venv ] || python3 -m venv .venv
	.venv/bin/pip3 install -r requirements.txt
	.venv/bin/pip3 install -r requirements-dev.txt

.PHONY: test

test:
	@. .venv/bin/activate && ./tests/test_api.sh && coverage report -m

start:
	@.venv/bin/python3 app.py

lint:
	@.venv/bin/flake8 *.py lib/*.py tests/*.py --exit-zero --statistics

fix:
	@.venv/bin/autopep8 --in-place --max-line-length=115 *.py lib/*.py tests/*.py

loc:
	@cloc $$(git ls-files)
	@echo "Without test files:"
	@cloc --exclude-dir=tests --include-lang=Python $$(git ls-files) | grep Python

tests/20533.concepts.ndjson:
	curl -s https://api.dante.gbv.de/export/download/kenom_material/default/kenom_material__default.jskos.ndjson | \
	jq -c 'del(.publisher,.qualifiedLiterals,.ancestors,.created,.modified,."@context",.issued,.mappings)' > $@
