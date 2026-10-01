"""Bounded browser-owned ephemeral candidates, never persistent study history."""
from collections import OrderedDict
from threading import RLock
from time import monotonic
from secrets import token_urlsafe


class CandidateCache:
    def __init__(self, limit=32, ttl=7200):
        self.entries = OrderedDict()
        self.limit = limit
        self.ttl = ttl
        self.lock = RLock()

    def put(self, owner, content, summary=None):
        with self.lock:
            for key, value in list(self.entries.items()):
                if monotonic() - value["created"] > self.ttl:
                    del self.entries[key]
            # Same candidate reanalysis keeps its conceptual identity.
            existing = next(
                (
                    key
                    for key, v in self.entries.items()
                    if v["owner"] == owner and v["content"] == content
                ),
                None,
            )
            key = existing or token_urlsafe(24)
            self.entries[key] = {
                "owner": owner,
                "content": content,
                "summary": summary,
                "created": monotonic(),
            }
            self.entries.move_to_end(key)
            while len(self.entries) > self.limit:
                self.entries.popitem(last=False)
            return key

    def get(self, owner, key):
        with self.lock:
            value = self.entries.get(key)
            if (
                not value
                or value["owner"] != owner
                or monotonic() - value["created"] > self.ttl
            ):
                raise KeyError(
                    "Candidate expired. Analyze the input again; saved study sessions remain available."
                )
            return value

    def recent(self, owner):
        with self.lock:
            return [
                (key, value)
                for key, value in reversed(self.entries.items())
                if value["owner"] == owner
                and monotonic() - value["created"] <= self.ttl
            ][:10]
