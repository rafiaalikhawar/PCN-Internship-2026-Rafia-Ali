.PHONY: help install test validate-config collect normalize detect-events build-graph

help:
	@echo "Available commands:"
	@echo "  make install          Install the project in editable mode"
	@echo "  make test             Run tests"
	@echo "  make validate-config  Validate configuration files"
	@echo "  make collect          Collect Open-Meteo data using configured defaults"
	@echo "  make normalize        Normalize cached Open-Meteo data"
	@echo "  make detect-events    Detect weather events from normalized data"
	@echo "  make build-graph      Build NetworkX graph outputs from detected events"
	@echo "  make help             Show this help message"

install:
	python3 -m pip install -e .

test:
	python3 -m pytest -q

validate-config:
	python3 -m weather_kg validate-config

collect:
	python3 -m weather_kg collect

normalize:
	python3 -m weather_kg normalize

detect-events:
	python3 -m weather_kg detect-events

build-graph:
	python3 -m weather_kg build-graph
