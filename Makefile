.PHONY: bootstrap run test verify check

bootstrap:
	python scripts/bootstrap_demo.py

run: bootstrap
	python -m quorava serve

test:
	python -m unittest discover -s tests -v

verify:
	python scripts/verify_demo.py

check:
	python scripts/check.py

