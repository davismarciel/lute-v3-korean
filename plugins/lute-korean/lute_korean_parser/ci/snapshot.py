"""One batched learner/representation snapshot; no lookup per candidate token."""
from dataclasses import dataclass
from hashlib import sha256
import json
from ..learner_state.engine import LearnerStateEngine
from ..knowledge.representation import (
    KnowledgeRepresentationService,
    CONSTRUCTION_COMPONENTS,
)


@dataclass(frozen=True)
class CILearnerSnapshot:
    """Canonical identity index and auditable learner/role/relation fingerprints."""

    items: dict
    roles: dict
    relations: tuple
    provenance: dict

    @classmethod
    def load(cls, session, as_of=None):
        """Calculate once, then read role/relation tables in two bounded batches."""
        export = LearnerStateEngine(session).export(as_of=as_of)
        representation = KnowledgeRepresentationService(session)
        available = representation.available()
        roles = (
            {row["item_id"]: row for row in representation.list_roles()}
            if available
            else {}
        )
        relations = representation.list_relations() if available else []
        by_id = {item["id"]: item for item in export["items"]}
        named = []
        for relation in relations:
            source = by_id.get(relation["source_item_id"])
            target = by_id.get(relation["target_item_id"])
            if source and target:
                named.append(
                    {
                        "source_item_id": source["type"] + ":" + source["identity"],
                        "target_item_id": target["type"] + ":" + target["identity"],
                        "relation_type": relation["relation_type"],
                    }
                )
        for sk, si, tk, ti, _ in CONSTRUCTION_COMPONENTS:
            row = {
                "source_item_id": sk + ":" + si,
                "target_item_id": tk + ":" + ti,
                "relation_type": "component_of",
            }
            if row not in named:
                named.append(row)
        provenance = {
            key: export[key]
            for key in [
                "policy_version",
                "policy_fingerprint",
                "as_of",
                "evidence_fingerprint",
                "input_fingerprint",
            ]
        }
        provenance["representation_fingerprint"] = sha256(
            json.dumps({"roles": roles, "relations": named}, sort_keys=True).encode()
        ).hexdigest()
        provenance["items"] = len(export["items"])
        return cls(
            {(item["type"], item["identity"]): item for item in export["items"]},
            roles,
            tuple(named),
            provenance,
        )
