install:
	uv sync --python 3.11

run:
	uv run -m fly_in $(ARGS)

debug:
	uv run -m pdb -m fly_in $(ARGS)

clean:
	find . -type f -name '*.py[co]' -delete
	rm -rf .mypy_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	uv run flake8 main.py fly_in
	uv run mypy main.py fly_in\
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs \
		--exclude '(^\.venv/)'

lint-strict:
	uv run flake8 *.py
	uv run mypy *.py --strict --exclude '(^\.venv/)'

.PHONY: install run debug clean lint lint-strict