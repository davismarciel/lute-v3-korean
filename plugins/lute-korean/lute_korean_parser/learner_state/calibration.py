"""Deterministic calibration sampling, never based on the manual labels."""


def select_sample(result, lexical_count=25):
    """Cover frequency, negatives and surface diversity, then include all grammar."""
    if lexical_count < 1:
        raise ValueError("Sample count must be positive")
    lexical = [s for s in result["items"] if s["type"] == "lexical"]
    frequent = sorted(
        lexical, key=lambda s: (-s["evidence"]["occurrences"], s["identity"])
    )
    rankings = [
        frequent,
        list(reversed(frequent)),
        frequent[len(frequent) // 3 : 2 * len(frequent) // 3],
        [s for s in frequent if s["evidence"]["anki_ratings"]["again"] > 0],
        [s for s in frequent if s["evidence"]["anki_ratings"]["again"] == 0],
        [s for s in frequent if len(s["evidence"]["surfaces"]) > 1],
        [s for s in frequent if len(s["evidence"]["surfaces"]) <= 1],
    ]
    chosen = []
    ids = set()
    while len(chosen) < min(lexical_count, len(lexical)):
        progress = False
        for ranking in rankings:
            while ranking and ranking[0]["id"] in ids:
                ranking.pop(0)
            if ranking and len(chosen) < lexical_count:
                state = ranking.pop(0)
                chosen.append(state)
                ids.add(state["id"])
                progress = True
        if not progress:
            break
    chosen += sorted(
        [s for s in result["items"] if s["type"] == "grammar"],
        key=lambda s: s["identity"],
    )
    return dict(
        result,
        items=chosen,
        sampling="deterministic frequency/Again/surface strata; labels not used",
    )
