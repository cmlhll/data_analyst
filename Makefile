.PHONY: test tdd-check

test:
	python -m pytest -q

tdd-check:
	python -m pytest -q --maxfail=1
