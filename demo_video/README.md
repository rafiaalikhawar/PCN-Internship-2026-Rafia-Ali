# Demo Video Instructions

The final assessment video should be a 5-10 minute screen recording with narration or captions. Record it from the completed local repository and dashboard.

## Recommended Recording Flow

1. Open the Streamlit dashboard:

   ```bash
   streamlit run app.py
   ```

2. Start on the dashboard Overview page and state that the selected assessment scope is Task 2: Weather Intelligence Knowledge Graph.

3. Show the implemented architecture:

   ```text
   Open-Meteo API -> raw cache -> normalized daily data -> event detection
   -> NetworkX knowledge graph -> graph-backed queries -> visualizations -> validation
   ```

4. Run the pipeline in offline/cache-only mode:

   ```bash
   python -m weather_kg run --cache-only
   ```

5. Show the configured locations in `config/locations.yaml`, including at least one neighbouring-country location such as Kabul, New Delhi, Zahedan, or Kashgar.

6. Show the generated graph evidence:

   - `data/graph/graph_summary.json`
   - dashboard Knowledge Graph -> Representative overview
   - dashboard Knowledge Graph -> Explore a neighbourhood

7. Run at least two graph-backed analytical queries live in the dashboard or CLI:

   ```bash
   python -m weather_kg query-graph highest-rainfall --country Pakistan --year 2022 --top 5
   python -m weather_kg query-graph cross-border-patterns --source-country Afghanistan --top 5
   ```

8. In the dashboard, show query provenance for the selected analytical pages so the viewer can see that results are calculated from the full GraphML graph.

9. Show validation:

   ```bash
   python -m weather_kg validate-submission
   pytest -q
   ```

10. Close with the completed scope and limitations:

    - completed: collection/cache, normalization, event detection, graph construction, six analytical queries, dashboard, saved visualizations, tests, validation
    - not claimed: official station records, confirmed floods, proven causation, forecasts, long-term climate attribution, or official vulnerability ranking

## Video Link

Add the final unlisted YouTube, Google Drive, or Loom URL here after recording:

```text
TO_BE_ADDED_AFTER_RECORDING
```
