"""Bounded ChatGPT-readable summaries, without raw reviews or full morphology."""
from copy import deepcopy


def compact_report(report, policy):
    """Explicit truncation retains categories/provenance while bounding text/detail."""

    def item(row):
        keys = [
            "kind",
            "identity",
            "bucket",
            "status",
            "confidence",
            "state_origin",
            "role",
            "tracked",
            "count",
            "contexts",
            "surfaces",
        ]
        result = {key: row[key] for key in keys if key in row}
        if "surfaces" in result:
            result["surfaces"] = result["surfaces"][: policy.compact_item_limit]
        if "sample" in row:
            result["sample"] = dict(
                row["sample"], text=row["sample"]["text"][: policy.compact_text_limit]
            )
        return result

    summary = deepcopy(report["summary"])
    for name in ["dense_clusters", "difficult_clusters"]:
        summary[name + "_total"] = len(summary[name])
        summary[name] = summary[name][: policy.compact_cluster_limit]
    hardest = [
        {
            key: segment[key]
            for key in ["index", "timestamp", "load", "reasons", "warnings"]
        }
        | {"text": segment["text"][: policy.compact_text_limit]}
        for segment in report["hardest_segments"]
    ]
    lexical = {
        key: report["lexical"][key]
        for key in [
            "occurrence_distribution",
            "unique_distribution",
            "supported_coverage",
            "previously_seen_coverage",
            "general_novelty",
        ]
    }
    lexical["proper_names"] = {
        "occurrence_distribution": report["lexical"]["proper_names"][
            "occurrence_distribution"
        ],
        "items": [
            item(row)
            for row in report["lexical"]["proper_names"]["items"][
                : policy.compact_item_limit
            ]
        ],
    }
    grammar = {
        key: report["grammar"][key]
        for key in [
            "label",
            "occurrence_distribution",
            "unique_distribution",
            "untracked_constructions_may_exist",
        ]
    }
    grammar["items"] = [item(row) for row in report["grammar"]["items"]]
    return {
        "schema_version": report["schema_version"],
        "compact": True,
        "content": report["content"],
        "policy": report["policy"],
        "learner_snapshot": report["learner_snapshot"],
        "processing_version": report["processing_version"],
        "summary": summary,
        "lexical": lexical,
        "grammar": grammar,
        "hardest_segments": hardest,
        "novelties": [
            item(row) for row in report["novelties"][: policy.compact_item_limit]
        ],
        "recycling": [
            item(row) for row in report["recycling"][: policy.compact_item_limit]
        ],
        "presented_opportunities": [
            item(row)
            for row in report["presented_opportunities"][: policy.compact_item_limit]
        ],
        "warnings": report["warnings"],
        "omissions": {
            "all_segments": True,
            "raw_morphology": True,
            "full_item_inventory": True,
            "text_limit": policy.compact_text_limit,
            "item_limit": policy.compact_item_limit,
            "cluster_limit": policy.compact_cluster_limit,
        },
        "diagnostics": report["diagnostics"],
    }


def compare_reports(reports):
    """Compare only supplied candidates, preserving individual explanation reports."""
    order = {"comfortable": 0, "productive": 1, "stretch": 2, "dense": 3, None: 4}
    rows = []
    for report in reports:
        row = {
            "content": report["content"]["name"],
            "fit": report["summary"]["fit"],
            "confidence": report["summary"]["confidence"],
            "supported_lexical_occurrence_coverage": report["lexical"][
                "supported_coverage"
            ],
            "untracked_lexical_occurrence_coverage": report["lexical"][
                "occurrence_distribution"
            ]["untracked"]["ratio"],
            "dense_segment_ratio": report["summary"]["dense_segment_ratio"],
            "tracked_grammar_novelty": sum(
                report["grammar"]["occurrence_distribution"][bucket]["count"]
                for bucket in ["untracked", "unassessed", "deferred"]
            ),
            "top_novelty_count": len(report["novelties"]),
            "report": report,
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            order[row["fit"]],
            row["dense_segment_ratio"],
            row["untracked_lexical_occurrence_coverage"],
            row["content"],
        )
    )
    return {
        "schema_version": 1,
        "comparison": "supplied candidate linguistic fit, not external discovery",
        "candidates": rows,
    }
