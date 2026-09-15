from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Protocol

from .models import GraphEdge, GraphNode


class ProvenanceViolation(RuntimeError):
    pass


class EvidenceAuthorizer(Protocol):
    """Narrow port implemented by the persistent evidence-ledger service."""

    def is_accepted(self, tenant_id: str, evidence_id: str) -> bool: ...


class GraphStore(Protocol):
    def put_node(self, node: GraphNode) -> None: ...
    def put_edge(self, edge: GraphEdge) -> None: ...
    def neighbours(
        self, tenant_id: str, node_id: str, predicate: str | None = None
    ) -> tuple[tuple[GraphEdge, GraphNode], ...]: ...


class InMemoryGraphStore:
    def __init__(self, evidence: EvidenceAuthorizer) -> None:
        self.evidence = evidence
        self._nodes: dict[tuple[str, str], GraphNode] = {}
        self._edges: dict[tuple[str, str], GraphEdge] = {}

    def put_node(self, node: GraphNode) -> None:
        self._nodes[(node.tenant_id, node.node_id)] = node

    def put_edge(self, edge: GraphEdge) -> None:
        source = self._nodes.get((edge.tenant_id, edge.source_id))
        target = self._nodes.get((edge.tenant_id, edge.target_id))
        if source is None or target is None:
            raise ProvenanceViolation("edge endpoints must exist in the same tenant")
        for evidence_id in edge.evidence_ids:
            if not self.evidence.is_accepted(edge.tenant_id, evidence_id):
                raise ProvenanceViolation(f"evidence {evidence_id} is not accepted")
        self._edges[(edge.tenant_id, edge.edge_id)] = edge

    def neighbours(
        self, tenant_id: str, node_id: str, predicate: str | None = None
    ) -> tuple[tuple[GraphEdge, GraphNode], ...]:
        result: list[tuple[GraphEdge, GraphNode]] = []
        for (edge_tenant, _), edge in self._edges.items():
            if edge_tenant != tenant_id or (predicate and edge.predicate != predicate):
                continue
            other = (
                edge.target_id
                if edge.source_id == node_id
                else edge.source_id
                if edge.target_id == node_id
                else None
            )
            if other and (node := self._nodes.get((tenant_id, other))):
                result.append((edge, node))
        return tuple(result)

    def traverse(
        self,
        tenant_id: str,
        start_id: str,
        *,
        max_depth: int = 2,
        edge_filter: Callable[[GraphEdge], bool] | None = None,
    ) -> tuple[GraphNode, ...]:
        visited = {start_id}
        queue = deque([(start_id, 0)])
        output: list[GraphNode] = []
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge, node in self.neighbours(tenant_id, current):
                if edge_filter and not edge_filter(edge):
                    continue
                if node.node_id not in visited:
                    visited.add(node.node_id)
                    output.append(node)
                    queue.append((node.node_id, depth + 1))
        return tuple(output)
