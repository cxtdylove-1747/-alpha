# Hypergraph JSON Client

`HypergraphClient` is a read-only adapter for:

- `kg_nodes.json`
- `kg_relations.json`
- `hypergraph_edges.json`

It builds in-memory indexes for fast lookup and supports:

- fuzzy node retrieval
- project context assembly
- similar project search
- consistency checks
- text-to-entity extraction (optional LLM callback)

## Quick usage

```python
from pathlib import Path
from apps.hypergraph.hypergraph_client import HypergraphClient

root = Path("C:/Users/Admin/PycharmProjects/智能体")
client = HypergraphClient(
    kg_nodes_path=root / "kg_nodes.json",
    kg_relations_path=root / "kg_relations.json",
    hypergraph_edges_path=root / "hypergraph_edges.json",
)

report = client.diagnose_project("Project_0001")
print(report["warnings"])
```

## Run tests

```powershell
Set-Location "C:\Users\Admin\PycharmProjects\智能体\backend"
python -m unittest apps.core.tests_hypergraph_client -v
```

