"""AnkiConnect API v6 read-only transport with bounded batches and timeouts."""
import requests
from .models import AnkiCardSnapshot, AnkiNoteSnapshot, AnkiReviewEvent, AnkiError
from .extraction import template_fields

READ_ACTIONS = {
    "version",
    "getActiveProfile",
    "findNotes",
    "notesInfo",
    "cardsInfo",
    "modelTemplates",
    "cardReviews",
    "getReviewsOfCards",
}


class AnkiConnectSourceAdapter:
    """Read-only AnkiConnect client; HTTP concerns stay within this adapter."""

    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport or requests.Session()
        self.transport.trust_env = False
        self._templates = {}

    def _call(self, action, **params):
        if action not in READ_ACTIONS:
            raise AnkiError("Only read-only Anki actions are permitted")
        try:
            response = self.transport.post(
                self.config.endpoint,
                json={"action": action, "version": 6, "params": params},
                timeout=self.config.timeout,
                allow_redirects=False,
            )
            if response.status_code in range(300, 400):
                raise AnkiError("Anki endpoint redirects are not allowed")
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AnkiError(f"AnkiConnect {action} failed: {exc}") from exc
        if not isinstance(payload, dict) or set(payload) != {"result", "error"}:
            raise AnkiError(f"Invalid response envelope for {action}")
        if payload["error"] is not None:
            raise AnkiError(f'AnkiConnect {action}: {payload["error"]}')
        return payload["result"]

    def _batches(self, ids):
        values = list(dict.fromkeys(ids))
        for start in range(0, len(values), self.config.batch_size):
            yield values[start : start + self.config.batch_size]

    def health(self):
        """Require API v6+ and the expected currently active profile."""
        self._templates.clear()
        version = self._call("version")
        if not isinstance(version, int) or version < 6:
            raise AnkiError("AnkiConnect API v6 or later is required")
        profile = self._call("getActiveProfile")
        if self.config.profile is not None and profile != self.config.profile:
            raise AnkiError("Active Anki profile differs from configured profile")
        return {"version": version, "profile": profile}

    def find_notes(self, query):
        """Discover real note IDs using the configured query."""
        return self._call("findNotes", query=query)

    def fetch_notes(self, note_ids):
        """Retrieve note content in bounded batches."""
        result = []
        for batch in self._batches(note_ids):
            for row in self._call("notesInfo", notes=batch):
                if row:
                    result.append(
                        AnkiNoteSnapshot(
                            row["noteId"],
                            row["modelName"],
                            {k: v["value"] for k, v in row["fields"].items()},
                            tuple(row["cards"]),
                            tuple(row["tags"]),
                            row.get("mod"),
                        )
                    )
        return result

    def fetch_cards(self, card_ids):
        """Retrieve scheduling and direction metadata once per card."""
        result = []
        for batch in self._batches(card_ids):
            for row in self._call("cardsInfo", cards=batch):
                if not row:
                    continue
                model = row["modelName"]
                if model not in self._templates:
                    self._templates[model] = self._call(
                        "modelTemplates", modelName=model
                    )
                templates = list(self._templates[model].items())
                ordinal = row.get("ord", row.get("fieldOrder", 0))
                template = (
                    templates[ordinal]
                    if 0 <= ordinal < len(templates)
                    else (templates[0] if len(templates) == 1 else ("unknown", {}))
                )
                metadata = {
                    k: row.get(k)
                    for k in (
                        "type",
                        "queue",
                        "due",
                        "reps",
                        "lapses",
                        "interval",
                        "factor",
                        "mod",
                    )
                }
                metadata.update(
                    template_name=template[0],
                    question_fields=template_fields(template[1].get("Front", "")),
                    answer_fields=template_fields(template[1].get("Back", "")),
                )
                result.append(
                    AnkiCardSnapshot(
                        row["cardId"], row["note"], row["deckName"], ordinal, metadata
                    )
                )
        return result

    def fetch_reviews(self, cards, cursors, full=False):
        """Fetch complete new-card histories and incremental known-card events."""
        # Preserve all raw review tuple fields.
        # pylint: disable=too-many-locals
        result = {}

        def retain(review):
            key = (review.card_id, review.review_id)
            if key in result and result[key] != review:
                raise AnkiError("Conflicting duplicate review returned by AnkiConnect")
            result[key] = review

        unseen = [c.card_id for c in cards if c.card_id not in cursors]
        if full:
            unseen = [c.card_id for c in cards]
        for batch in self._batches(unseen):
            payload = self._call("getReviewsOfCards", cards=batch)
            for card_id, reviews in payload.items():
                for row in reviews:
                    review = AnkiReviewEvent(
                        row["id"],
                        int(card_id),
                        row["ease"],
                        row["ivl"],
                        row["lastIvl"],
                        row["type"],
                        row["time"],
                        row.get("factor", 0),
                        row.get("usn", 0),
                    )
                    retain(review)
        if not full:
            known = {c.card_id: c for c in cards if c.card_id in cursors}
            for deck in sorted({c.deck for c in known.values()}):
                ids = {cid for cid, c in known.items() if c.deck == deck}
                # AnkiConnect has a deck-level cursor API; filter its result per card.
                start = min(cursors[cid] for cid in ids)
                for row in self._call("cardReviews", deck=deck, startID=start):
                    (
                        rid,
                        cid,
                        usn,
                        rating,
                        interval,
                        previous,
                        factor,
                        duration,
                        kind,
                    ) = row
                    if cid in ids and rid > cursors[cid]:
                        retain(
                            AnkiReviewEvent(
                                rid,
                                cid,
                                rating,
                                interval,
                                previous,
                                kind,
                                duration,
                                factor,
                                usn,
                            )
                        )
        return list(result.values())
