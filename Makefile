.PHONY: install init collect analyze report daily test

install:
	python -m pip install -e ".[dev]"

init:
	frontier-signal init-db

collect:
	frontier-signal collect

analyze:
	frontier-signal analyze --limit 100

report:
	frontier-signal report --hours 30

daily:
	frontier-signal run-daily

test:
	pytest -q
