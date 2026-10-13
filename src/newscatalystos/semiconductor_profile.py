"""5_1 SemiconductorProfile v1: one-industry vocabulary and impact paths.

Classification is a deterministic taxonomy, NOT a list of beneficiary stocks,
contract counterparties, supply agreements or quantified earnings effects.
No multi-industry expansion is permitted in this V1.0 component.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .source_share import SourceShareError

SCHEMA="newscatalyst.semiconductor_profile.v1"
INDUSTRY="SEMICONDUCTOR"
STAGES=(
    "MEMORY_DRAM", "MEMORY_NAND", "MEMORY_HBM",
    "WAFER_FAB", "FAB_EQUIPMENT", "MATERIALS",
    "SUBSTRATES", "ADVANCED_PACKAGING", "TESTING",
)
CAUSES=(
    "MEMORY_PRICE", "VOLUME", "EQUIPMENT_CAPEX",
    "MATERIAL_CONSUMPTION", "PACKAGING_CAPACITY",
    "TESTING_DEMAND", "TECHNOLOGY_YIELD",
)
LINKS={
    "MEMORY_PRICE": ("MEMORY_DRAM","MEMORY_NAND","MEMORY_HBM"),
    "VOLUME": ("WAFER_FAB","MATERIALS","SUBSTRATES"),
    "EQUIPMENT_CAPEX": ("FAB_EQUIPMENT","WAFER_FAB"),
    "MATERIAL_CONSUMPTION": ("MATERIALS","WAFER_FAB"),
    "PACKAGING_CAPACITY": ("MEMORY_HBM","ADVANCED_PACKAGING","SUBSTRATES"),
    "TESTING_DEMAND": ("TESTING","MEMORY_HBM","MEMORY_DRAM","MEMORY_NAND"),
    "TECHNOLOGY_YIELD": ("WAFER_FAB","FAB_EQUIPMENT","TESTING"),
}


@dataclass(frozen=True)
class ProfileNode:
    node_id: str
    stage: str
    descriptions: tuple[str, ...]


@dataclass(frozen=True)
class ImpactRoute:
    trigger: str
    candidate_stages: tuple[str, ...]
    transmission_kind: str = "HYPOTHESIS_ONLY_NOT_CAUSAL_PROOF"


@dataclass(frozen=True)
class SemiconductorProfile:
    schema_version: str
    industry_id: str
    nodes: tuple[ProfileNode, ...]
    routes: tuple[ImpactRoute, ...]
    taxonomy_sha256: str
    unverified_relationship_count: int = 0
    verified_beneficiary_count: int = 0
    annual_revenue_inference_allowed: bool = False

    def route_for(self, trigger: str) -> ImpactRoute:
        if trigger not in CAUSES:
            raise SourceShareError("non-semiconductor economic trigger excluded")
        return next(r for r in self.routes if r.trigger==trigger)


def build_semiconductor_profile() -> SemiconductorProfile:
    nodes=tuple(ProfileNode(f"SEMICONDUCTOR:{x}",x,(
        "Sector category only: relationship and sales contribution need evidence",
    )) for x in STAGES)
    routes=tuple(ImpactRoute(trigger,tuple(LINKS[trigger])) for trigger in CAUSES)
    doc={"schema":SCHEMA,"industry":INDUSTRY,
         "nodes":[n.node_id for n in nodes],
         "routes":{r.trigger:list(r.candidate_stages) for r in routes}}
    digest=sha256(json.dumps(doc,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return SemiconductorProfile(SCHEMA,INDUSTRY,nodes,routes,digest)


def validate_profile(profile: SemiconductorProfile) -> None:
    if not isinstance(profile,SemiconductorProfile) or (
        profile.schema_version!=SCHEMA or profile.industry_id!=INDUSTRY
    ):
        raise SourceShareError("V1.0 only supports semiconductor profile")
    expected=build_semiconductor_profile()
    if profile!=expected:
        raise SourceShareError("unreviewed profile or beneficiary claims not permitted")
