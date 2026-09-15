from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeKind(StrEnum):
    PUBLICATION = "publication"
    PREPRINT = "preprint"
    PATENT = "patent"
    PATENT_FAMILY = "patent_family"
    PERSON = "person"
    INSTITUTION = "institution"
    FUNDER = "funder"
    COUNTRY = "country"
    TOPIC = "topic"
    METHOD = "method"
    MATERIAL = "material"
    DATASET = "dataset"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    POLICY = "policy"


class AssertionKind(StrEnum):
    SOURCE_REPORTED = "source_reported"
    EXTRACTED = "extracted"
    MODEL_INFERRED = "model_inferred"
    HUMAN_VALIDATED = "human_validated"
    DISPUTED = "disputed"


class GraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)
    node_id: str
    tenant_id: str
    kind: NodeKind
    label: str
    properties: Mapping[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)
    edge_id: str
    tenant_id: str
    source_id: str
    target_id: str
    predicate: str
    assertion_kind: AssertionKind
    evidence_ids: tuple[str, ...]
    valid_from: str | None = None
    valid_to: str | None = None
    properties: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence_is_required(self) -> GraphEdge:
        if not self.evidence_ids:
            raise ValueError("graph edges require evidence")
        return self
