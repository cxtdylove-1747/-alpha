from __future__ import annotations

from typing import Any, Dict, Optional

from django.apps import apps

IGNORED_GRAPH_OPERATIONS = {
    "admin_hypergraph_preview",
    "admin_knowledge_graph_preview",
}


def track_graph_call(
    *,
    graph_type: str,
    operation: str,
    source: str,
    success: bool,
    user_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist graph usage for admin observability; failures should not break business flow."""
    if str(operation or "").strip() in IGNORED_GRAPH_OPERATIONS:
        return
    try:
        model = apps.get_model("core", "GraphInvocationLog")
        model.objects.create(
            graph_type=graph_type,
            operation=operation,
            source=source,
            success=bool(success),
            user_id=user_id,
            plan_id=plan_id,
            detail=detail or {},
        )
    except Exception:
        # Observability must be best-effort.
        return


