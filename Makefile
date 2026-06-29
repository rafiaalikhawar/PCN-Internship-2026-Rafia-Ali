.PHONY: help install test validate-config

help:
	@echo "Available commands:"
	@echo "  make install          Install the project in editable mode"
	@echo "  make test             Run tests"
	@echo "  make validate-config  Validate configuration files"
	@echo "  make help             Show this help message"

install:
	python3 -m pip install -e .

test:
	python3 -m pytest -q

validate-config:
	python3 -m weather_kg validate-config
