import pytest

from pekua.graph import (
    AssertionKind,
    GraphEdge,
    GraphNode,
    InMemoryGraphStore,
    NodeKind,
    ProvenanceViolation,
)


class EvidenceFixture:
    def __init__(self) -> None:
        self.accepted: set[tuple[str, str]] = set()

    def is_accepted(self, tenant_id: str, evidence_id: str) -> bool:
        return (tenant_id, evidence_id) in self.accepted


def edge() -> GraphEdge:
    return GraphEdge(
        edge_id="edge-1",
        tenant_id="tenant-a",
        source_id="a",
        target_id="b",
        predicate="SUPPORTS",
        assertion_kind=AssertionKind.EXTRACTED,
        evidence_ids=("ev-1",),
    )


def test_only_accepted_evidence_can_create_edge() -> None:
    evidence = EvidenceFixture()
    graph = InMemoryGraphStore(evidence)
    graph.put_node(GraphNode(node_id="a", tenant_id="tenant-a", kind=NodeKind.CLAIM, label="A"))
    graph.put_node(GraphNode(node_id="b", tenant_id="tenant-a", kind=NodeKind.TOPIC, label="B"))
    with pytest.raises(ProvenanceViolation):
        graph.put_edge(edge())
    evidence.accepted.add(("tenant-a", "ev-1"))
    graph.put_edge(edge())
    assert graph.neighbours("tenant-a", "a")[0][1].node_id == "b"


def test_nodes_are_isolated_by_tenant() -> None:
    evidence = EvidenceFixture()
    graph = InMemoryGraphStore(evidence)
    graph.put_node(GraphNode(node_id="a", tenant_id="tenant-a", kind=NodeKind.CLAIM, label="A"))
    graph.put_node(GraphNode(node_id="b", tenant_id="tenant-b", kind=NodeKind.TOPIC, label="B"))
    evidence.accepted.add(("tenant-a", "ev-1"))
    with pytest.raises(ProvenanceViolation, match="same tenant"):
        graph.put_edge(edge())
