.PHONY: test tdd-check

test:
	pytest -q

tdd-check:
	pytest -q --maxfail=1
