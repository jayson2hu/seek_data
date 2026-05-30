.PHONY: test l1-smoke l1-dod

test:
	python -m pytest

l1-smoke:
	python -m l1_data_processing.smoke

l1-dod:
	python -m l1_data_processing.dod
