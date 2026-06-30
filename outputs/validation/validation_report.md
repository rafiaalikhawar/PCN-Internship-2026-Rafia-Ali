# Submission Validation Report

- Overall status: **PASS**
- Validation timestamp: `2026-06-30T21:31:34Z`
- Checks: 98/98 passed
- Determinism note: the timestamp changes between runs; compare check results semantically.

## Checks

| Category | Check | Status | Observed | Required | Path | Message |
|---|---|---|---|---|---|---|
| input_coverage | location_registry_exists | PASS | 22 | > 0 locations | `config/locations.yaml` | Check passed. |
| input_coverage | normalized_daily_exists | PASS | 40172 | > 0 rows | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | coverage_summary_exists | PASS | dict | non-empty JSON object | `data/processed/data_coverage.json` | Check passed. |
| input_coverage | collection_summary_exists | PASS | 4087 | > 0 bytes | `data/processed/collection_summary.json` | Check passed. |
| input_coverage | configured_location_count | PASS | 22 | 22 | `config/locations.yaml` | Check passed. |
| input_coverage | configured_countries | PASS | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | `config/locations.yaml` | Check passed. |
| input_coverage | daily_required_columns | PASS | ["admin_region", "api_elevation_m", "api_latitude", "api_longitude", "corridor", "country", "country_code", "date", "day", "epidemiological_week", "iso_week_year", "latitude", "location_id", "location_kind", "location_name", "longitude", "month", "precipitation_hours", "precipitation_mm", "rain_mm", "retrieved_at", "source_cache_file", "source_name", "source_timezone", "temperature_max_c", "temperature_mean_c", "temperature_min_c", "weather_code", "wind_gusts_max_kmh", "wind_speed_max_kmh", "year"] | ["country", "date", "location_id", "source_cache_file", "source_name"] | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | daily_valid_dates | PASS | 40172 | 40172 | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | daily_unique_location_dates | PASS | 0 | 0 | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | daily_location_count | PASS | 22 | 22 | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | daily_country_coverage | PASS | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | daily_date_scope | PASS | ["2021-01-01", "2025-12-31"] | ["2021-01-01", "2025-12-31"] | `data/processed/daily_weather.csv` | Check passed. |
| input_coverage | coverage_date_scope | PASS | ["2021-01-01", "2025-12-31"] | ["2021-01-01", "2025-12-31"] | `data/processed/data_coverage.json` | Check passed. |
| events | event_output_exists | PASS | 6693 | > 0 rows | `data/processed/weather_events.csv` | Check passed. |
| events | event_summary_exists | PASS | 1592 | > 0 bytes | `data/processed/event_detection_summary.json` | Check passed. |
| events | event_required_columns | PASS | ["absolute_threshold", "caveat", "country", "critical_rolling_precipitation_mm", "critical_window_end", "critical_window_start", "derivation_method", "duration_days", "end_date", "event_id", "event_subtype", "event_type", "inferred", "location_id", "location_name", "lookback_days", "maximum_daily_precipitation_mm", "maximum_temperature_c", "maximum_wind_gusts_kmh", "maximum_wind_speed_kmh", "minimum_temperature_c", "percentile_threshold", "related_rainfall_event_id", "related_wind_event_id", "rolling_precipitation_mm", "severity_percentile", "severity_score", "severity_score_raw", "source_dataset", "source_date_end", "source_date_start", "start_date", "status", "total_precipitation_mm"] | ["event_id", "event_type", "event_subtype", "status", "location_id", "location_name", "country", "start_date", "end_date", "duration_days", "total_precipitation_mm", "maximum_daily_precipitation_mm", "maximum_temperature_c", "minimum_temperature_c", "maximum_wind_speed_kmh", "maximum_wind_gusts_kmh", "rolling_precipitation_mm", "lookback_days", "critical_window_start", "critical_window_end", "critical_rolling_precipitation_mm", "percentile_threshold", "absolute_threshold", "severity_score", "severity_score_raw", "severity_percentile", "related_rainfall_event_id", "related_wind_event_id", "derivation_method", "source_date_start", "source_date_end", "source_dataset", "inferred", "caveat"] | `data/processed/weather_events.csv` | Check passed. |
| events | required_event_types | PASS | ["Drought", "Flood", "Heatwave", "Rainfall", "Storm", "Temperature", "Wind"] | ["Drought", "Flood", "Heatwave", "Rainfall", "Storm", "Temperature", "Wind"] | `data/processed/weather_events.csv` | Check passed. |
| events | unique_event_ids | PASS | 0 | 0 | `data/processed/weather_events.csv` | Check passed. |
| events | event_date_order | PASS | 6693 | 6693 | `data/processed/weather_events.csv` | Check passed. |
| events | event_duration | PASS | 6693 | 6693 | `data/processed/weather_events.csv` | Check passed. |
| events | event_provenance | PASS | ["source_date_start", "source_date_end", "source_dataset", "derivation_method"] | ["source_date_start", "source_date_end", "source_dataset", "derivation_method"] | `data/processed/weather_events.csv` | Check passed. |
| events | storm_supporting_events | PASS | 166 | valid Rainfall and Wind references | `data/processed/weather_events.csv` | Check passed. |
| events | flood_inference_labels | PASS | 306 | inferred_candidate with caveat | `data/processed/weather_events.csv` | Check passed. |
| events | drought_indicator_labels | PASS | 226 | derived_indicator with caveat | `data/processed/weather_events.csv` | Check passed. |
| graph | graph_nodes_exist | PASS | 12503 | > 0 rows | `data/graph/nodes.csv` | Check passed. |
| graph | graph_relationships_exist | PASS | 45187 | > 0 rows | `data/graph/relationships.csv` | Check passed. |
| graph | graph_summary_exists | PASS | dict | non-empty JSON object | `data/graph/graph_summary.json` | Check passed. |
| graph | graph_json_exists | PASS | 54407615 | > 0 bytes | `data/graph/weather_knowledge_graph.json` | Check passed. |
| graph | graphml_exists | PASS | 38366649 | > 0 bytes | `data/graph/weather_knowledge_graph.graphml` | Check passed. |
| graph | graph_node_schema | PASS | ["absolute_threshold", "admin_region", "caveat", "corridor", "country", "country_code", "critical_rolling_precipitation_mm", "critical_window_end", "critical_window_start", "date", "derivation_method", "duration_days", "end_date", "event_count", "event_id", "event_subtype", "event_type", "indicator_name", "inferred", "label", "latitude", "location_id", "location_kind", "location_name", "longitude", "lookback_days", "maximum_daily_precipitation_mm", "maximum_severity_percentile", "maximum_temperature_c", "maximum_wind_gusts_kmh", "maximum_wind_speed_kmh", "mean_severity_percentile", "method", "minimum_temperature_c", "node_id", "node_type", "percentile_threshold", "provenance", "related_rainfall_event_id", "related_wind_event_id", "severity_percentile", "severity_score_raw", "source", "source_dataset", "start_date", "status", "total_precipitation_mm", "year"] | ["country", "event_id", "node_id", "node_type"] | `data/graph/nodes.csv` | Check passed. |
| graph | graph_relationship_schema | PASS | ["caveat", "confidence", "event_type_mapping", "evidence_type", "inference_status", "lag_days", "method", "provenance", "relationship_id", "relationship_type", "source_country", "source_event_id", "source_id", "source_location", "target_country", "target_event_id", "target_id", "target_location"] | ["relationship_id", "relationship_type", "source_id", "target_id"] | `data/graph/relationships.csv` | Check passed. |
| graph | graph_node_minimum | PASS | 12503 | 200 | `data/graph/nodes.csv` | Check passed. |
| graph | graph_relationship_minimum | PASS | 45187 | 350 | `data/graph/relationships.csv` | Check passed. |
| graph | required_node_types | PASS | ["Climate Indicator", "Country", "Date", "Drought", "Flood", "Heatwave", "Location", "Rainfall Event", "Storm", "Temperature Event", "Time Window", "Wind Event"] | ["Climate Indicator", "Country", "Date", "Drought", "Flood", "Heatwave", "Location", "Rainfall Event", "Storm", "Temperature Event", "Time Window", "Wind Event"] | `data/graph/nodes.csv` | Check passed. |
| graph | required_relationship_types | PASS | ["AFFECTED", "ASSOCIATED_WITH", "CAUSED", "ENDED_ON", "FOLLOWED", "LOCATED_IN", "OCCURRED_IN", "PRECEDED", "STARTED_ON", "UPSTREAM_OF", "WITHIN_TIME_WINDOW"] | ["AFFECTED", "ASSOCIATED_WITH", "CAUSED", "FOLLOWED", "OCCURRED_IN", "PRECEDED", "UPSTREAM_OF"] | `data/graph/relationships.csv` | Check passed. |
| graph | unique_node_ids | PASS | 0 | 0 | `data/graph/nodes.csv` | Check passed. |
| graph | unique_relationship_ids | PASS | 0 | 0 | `data/graph/relationships.csv` | Check passed. |
| graph | no_dangling_endpoints | PASS | 0 | 0 | `data/graph/relationships.csv` | Check passed. |
| graph | graph_country_coverage | PASS | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | ["Afghanistan", "China", "India", "Iran", "Pakistan"] | `data/graph/nodes.csv` | Check passed. |
| graph | event_occurred_in_cardinality | PASS | 6693 | exactly one valid target for 6693 events | `data/graph/relationships.csv` | Check passed. |
| graph | location_located_in_cardinality | PASS | 22 | one valid country for 22 locations | `data/graph/relationships.csv` | Check passed. |
| graph | upstream_candidate_direction | PASS | 1879 | non-Pakistan source to Pakistan target with candidate caveat | `data/graph/relationships.csv` | Check passed. |
| graph | caused_derivation_labels | PASS | 332 | algorithmic_derivation with non-causation caveat | `data/graph/relationships.csv` | Check passed. |
| graph | preceded_followed_consistency | PASS | 0 | 0 | `data/graph/relationships.csv` | Check passed. |
| graph | graph_summary_counts | PASS | [12503, 45187] | [12503, 45187] | `data/graph/graph_summary.json` | Check passed. |
| graph | graph_json_counts | PASS | [12503, 45187] | [12503, 45187] | `data/graph/weather_knowledge_graph.json` | Check passed. |
| graph | graphml_reload_and_counts | PASS | [12503, 45187] | [12503, 45187] | `data/graph/weather_knowledge_graph.graphml` | Check passed. |
| analysis | analysis_file_highest_rainfall.csv | PASS | 4176 | > 0 bytes | `data/analysis/highest_rainfall.csv` | Check passed. |
| analysis | analysis_nonempty_highest_rainfall.csv | PASS | 20 | > 0 rows | `data/analysis/highest_rainfall.csv` | Check passed. |
| analysis | analysis_schema_highest_rainfall.csv | PASS | ["caveat", "country", "end_date", "event_id", "location_id", "location_name", "maximum_daily_precipitation_mm", "percentile_threshold", "rank", "severity_percentile", "start_date", "status", "total_precipitation_mm"] | ["event_id", "location_id", "maximum_daily_precipitation_mm", "rank"] | `data/analysis/highest_rainfall.csv` | Check passed. |
| analysis | analysis_file_multi_event_locations.csv | PASS | 5787 | > 0 bytes | `data/analysis/multi_event_locations.csv` | Check passed. |
| analysis | analysis_nonempty_multi_event_locations.csv | PASS | 22 | > 0 rows | `data/analysis/multi_event_locations.csv` | Check passed. |
| analysis | analysis_schema_multi_event_locations.csv | PASS | ["country", "distinct_event_type_count", "event_types", "events_by_type", "location_id", "location_kind", "location_name", "maximum_severity_percentile", "mean_severity_percentile", "total_event_count", "years_with_detected_events"] | ["country", "distinct_event_type_count", "location_id", "total_event_count"] | `data/analysis/multi_event_locations.csv` | Check passed. |
| analysis | analysis_file_cooccurring_patterns.csv | PASS | 4258 | > 0 bytes | `data/analysis/cooccurring_patterns.csv` | Check passed. |
| analysis | analysis_nonempty_cooccurring_patterns.csv | PASS | 21 | > 0 rows | `data/analysis/cooccurring_patterns.csv` | Check passed. |
| analysis | analysis_schema_cooccurring_patterns.csv | PASS | ["algorithmically_related_pair_count", "caveat", "distinct_country_count", "distinct_location_count", "event_type_pair", "example_event_ids", "includes_algorithmic_derivation", "median_gap_days", "total_pair_count"] | ["caveat", "event_type_pair", "total_pair_count"] | `data/analysis/cooccurring_patterns.csv` | Check passed. |
| analysis | analysis_file_climate_indicator_trends.csv | PASS | 27911 | > 0 bytes | `data/analysis/climate_indicator_trends.csv` | Check passed. |
| analysis | analysis_nonempty_climate_indicator_trends.csv | PASS | 153 | > 0 rows | `data/analysis/climate_indicator_trends.csv` | Check passed. |
| analysis | analysis_schema_climate_indicator_trends.csv | PASS | ["absolute_change", "available_years", "caveat", "country", "direction", "event_type", "final_year", "final_year_value", "first_year", "first_year_value", "indicator_name", "linear_slope", "location_id"] | ["caveat", "direction", "event_type", "linear_slope", "location_id"] | `data/analysis/climate_indicator_trends.csv` | Check passed. |
| analysis | analysis_file_climate_indicator_annual_values.csv | PASS | 132803 | > 0 bytes | `data/analysis/climate_indicator_annual_values.csv` | Check passed. |
| analysis | analysis_nonempty_climate_indicator_annual_values.csv | PASS | 765 | > 0 rows | `data/analysis/climate_indicator_annual_values.csv` | Check passed. |
| analysis | analysis_schema_climate_indicator_annual_values.csv | PASS | ["annual_value", "caveat", "country", "event_type", "indicator_name", "location_id", "value_source", "year"] | ["annual_value", "event_type", "location_id", "year"] | `data/analysis/climate_indicator_annual_values.csv` | Check passed. |
| analysis | analysis_file_weather_exposure_ranking.csv | PASS | 7133 | > 0 bytes | `data/analysis/weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_nonempty_weather_exposure_ranking.csv | PASS | 22 | > 0 rows | `data/analysis/weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_schema_weather_exposure_ranking.csv | PASS | ["active_year_list", "active_years", "country", "distinct_event_types", "diversity_component", "event_types", "exposure_score", "frequency_component", "location_id", "location_name", "methodology_caveat", "overall_rank", "recurrence_component", "severity_component", "total_events"] | ["country", "exposure_score", "location_id", "methodology_caveat", "severity_component"] | `data/analysis/weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_file_pakistan_weather_exposure_ranking.csv | PASS | 2771 | > 0 bytes | `data/analysis/pakistan_weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_nonempty_pakistan_weather_exposure_ranking.csv | PASS | 8 | > 0 rows | `data/analysis/pakistan_weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_schema_pakistan_weather_exposure_ranking.csv | PASS | ["active_year_list", "active_years", "country", "distinct_event_types", "diversity_component", "event_types", "exposure_score", "frequency_component", "location_id", "location_name", "methodology_caveat", "overall_rank", "pakistan_rank", "recurrence_component", "severity_component", "total_events"] | ["country", "exposure_score", "location_id", "methodology_caveat", "pakistan_rank"] | `data/analysis/pakistan_weather_exposure_ranking.csv` | Check passed. |
| analysis | analysis_file_cross_border_precursor_edges.csv | PASS | 673385 | > 0 bytes | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | analysis_nonempty_cross_border_precursor_edges.csv | PASS | 1879 | > 0 rows | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | analysis_schema_cross_border_precursor_edges.csv | PASS | ["caveat", "confidence", "event_type_mapping", "evidence_type", "inference_status", "lag_days", "method", "source_country", "source_event_id", "source_location", "target_event_id", "target_pakistani_location"] | ["caveat", "source_country", "source_event_id", "target_event_id", "target_pakistani_location"] | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | analysis_file_cross_border_lag_summary.csv | PASS | 86402 | > 0 bytes | `data/analysis/cross_border_lag_summary.csv` | Check passed. |
| analysis | analysis_nonempty_cross_border_lag_summary.csv | PASS | 375 | > 0 rows | `data/analysis/cross_border_lag_summary.csv` | Check passed. |
| analysis | analysis_schema_cross_border_lag_summary.csv | PASS | ["caveat", "earliest_example", "event_type_mapping", "latest_example", "maximum_lag_days", "mean_lag_days", "median_lag_days", "minimum_lag_days", "relationship_count", "source_country", "source_location", "target_pakistani_location"] | ["caveat", "median_lag_days", "source_country", "target_pakistani_location"] | `data/analysis/cross_border_lag_summary.csv` | Check passed. |
| analysis | analysis_file_analysis_summary.json | PASS | 7468 | > 0 bytes | `data/analysis/analysis_summary.json` | Check passed. |
| analysis | highest_rainfall_ranking_method | PASS | maximum_daily_precipitation_mm | descending maximum daily precipitation | `data/analysis/highest_rainfall.csv` | Check passed. |
| analysis | exposure_score_bounds | PASS | [0.638513, 0.871901] | 0 through 1 | `data/analysis/weather_exposure_ranking.csv` | Check passed. |
| analysis | exposure_uses_percentile_component | PASS | ["overall_rank", "location_id", "location_name", "country", "total_events", "distinct_event_types", "event_types", "active_years", "active_year_list", "frequency_component", "diversity_component", "severity_component", "recurrence_component", "exposure_score", "methodology_caveat"] | severity_component without severity_score_raw | `data/analysis/weather_exposure_ranking.csv` | Check passed. |
| analysis | pakistan_ranking_scope | PASS | ["Pakistan"] | ["Pakistan"] | `data/analysis/pakistan_weather_exposure_ranking.csv` | Check passed. |
| analysis | cross_border_uses_upstream_only | PASS | 1879 | subset of UPSTREAM_OF event pairs | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | cross_border_targets_pakistan | PASS | 1879 | all targets in Pakistan | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | cross_border_candidate_caveats | PASS | true | true | `data/analysis/cross_border_precursor_edges.csv` | Check passed. |
| analysis | analytical_language_safety | PASS | [] | [] | `data/analysis` | Check passed. |
| deliverables | dashboard_app_exists | PASS | 70906 | > 0 bytes | `app.py` | Check passed. |
| deliverables | dashboard_helper_exists | PASS | 15513 | > 0 bytes | `src/weather_kg/dashboard.py` | Check passed. |
| deliverables | dashboard_tests_exist | PASS | 14586 | > 0 bytes | `tests/test_dashboard.py` | Check passed. |
| deliverables | readme_exists | PASS | 15865 | > 0 bytes | `README.md` | Check passed. |
| deliverables | technical_report_source_exists | PASS | 7860 | > 0 bytes | `reports/technical_report.md` | Check passed. |
| deliverables | saved_folium_map_exists | PASS | 36162 | > 0 bytes | `outputs/maps/weather_locations.html` | Check passed. |
| deliverables | saved_pyvis_graph_exists | PASS | 959130 | > 0 bytes | `outputs/graph/weather_knowledge_graph.html` | Check passed. |
| deliverables | visualization_manifest_exists | PASS | 4355 | > 0 bytes | `outputs/visualization_manifest.json` | Check passed. |
| deliverables | figure_top_daily_rainfall.png | PASS | 85032 | > 0 bytes | `outputs/figures/top_daily_rainfall.png` | Check passed. |
| deliverables | figure_multi_event_locations.png | PASS | 97251 | > 0 bytes | `outputs/figures/multi_event_locations.png` | Check passed. |
| deliverables | figure_cooccurring_event_patterns.png | PASS | 80761 | > 0 bytes | `outputs/figures/cooccurring_event_patterns.png` | Check passed. |
| deliverables | figure_climate_indicator_trends.png | PASS | 160825 | > 0 bytes | `outputs/figures/climate_indicator_trends.png` | Check passed. |
| deliverables | figure_weather_exposure_ranking.png | PASS | 69766 | > 0 bytes | `outputs/figures/weather_exposure_ranking.png` | Check passed. |
| deliverables | figure_cross_border_lag_patterns.png | PASS | 155897 | > 0 bytes | `outputs/figures/cross_border_lag_patterns.png` | Check passed. |
| deliverables | dashboard_import | PASS | imported without server startup | successful import without server | `app.py` | Check passed. |

## Remaining Deliverable Warnings

