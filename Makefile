.PHONY: test l1-smoke

test:
	python -m pytest

l1-smoke:
	python -m l1_data_processing.smoke
