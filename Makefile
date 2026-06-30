.PHONY: help install pipeline pipeline-cached test validate visualizations validate-config collect normalize detect-events build-graph analyze dashboard

help:
	@echo "Available commands:"
	@echo "  make install          Install the project in editable mode"
	@echo "  make pipeline         Run the complete pipeline"
	@echo "  make pipeline-cached  Run the complete pipeline using cache only"
	@echo "  make test             Run tests"
	@echo "  make validate         Validate the complete submission offline"
	@echo "  make visualizations   Export saved map, graph, and report figures"
	@echo "  make validate-config  Validate configuration files"
	@echo "  make collect          Collect Open-Meteo data using configured defaults"
	@echo "  make normalize        Normalize cached Open-Meteo data"
	@echo "  make detect-events    Detect weather events from normalized data"
	@echo "  make build-graph      Build NetworkX graph outputs from detected events"
	@echo "  make analyze          Run analytical queries from graph outputs"
	@echo "  make dashboard        Launch the Streamlit research dashboard"
	@echo "  make help             Show this help message"

install:
	python3 -m pip install -e .

pipeline:
	python3 -m weather_kg run

pipeline-cached:
	python3 -m weather_kg run --cache-only

test:
	pytest -q

validate:
	python3 -m weather_kg validate-submission

visualizations:
	python3 -m weather_kg export-visualizations

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

analyze:
	python3 -m weather_kg analyze

dashboard:
	streamlit run app.py
