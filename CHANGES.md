# CHANGES

## build_high_quality.py

### 1) Hyperedge logic relaxed (default)
- Updated `stage3_build_graph` to support **document-level co-occurrence** hyperedge creation for:
  - `ValueLoop`
  - `RiskPattern`
  - `ResourceLeverage`
  - `PitchLogic`
- New evidence payload for relaxed edges includes:
  - `file`
  - `text` (co-occurrence explanation)
  - `competition`
  - `evidence_type=document_cooccurrence`

### 2) Quality guard preserved
- Added source-trace filter helpers:
  - `_node_has_file_source(...)`
  - `_ids_with_doc_source(...)`
- Relaxed-mode edges are only built when involved nodes are sourced from the **current document file**, preserving traceability.

### 3) Strict mode switch added
- Added CLI argument: `--strict-hyperedge`
- Added global default: `STRICT_HYPEREDGE = False`
- `main()` now passes this switch into `stage3_build_graph(...)`.
- When `--strict-hyperedge` is enabled, original sentence-level strict logic is used.

### 4) CompetitionShadow unchanged
- `CompetitionShadow` generation logic remains the same (still requires explicit giant mention evidence).

