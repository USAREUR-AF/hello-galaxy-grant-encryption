"""zenoh_bus — the same bus interface as demo.InProcessBus, over a REAL router.

Used only by `./bin/grant-enc 03 --fabric`. It carries the *identical* envelope +
bundle bytes over a live eclipse/zenoh 1.9 router, proving the transport claim on
real infrastructure. Everything else in the repo runs without it.

Setup (see local-fabric/README.md):
    docker compose -f local-fabric/docker-compose.yml up -d   # a router on tcp/127.0.0.1:7447
    pip install eclipse-zenoh                                 # the client
    ./bin/grant-enc 03 --fabric

Targets eclipse-zenoh 1.x. Payload/reply accessors are read defensively so a
minor API drift degrades to a clear error (scenario 03 then falls back to the
in-process bus) rather than a confusing crash.
"""
from __future__ import annotations

import json
import time
from typing import Callable

import zenoh   # provided by `pip install eclipse-zenoh`; imported lazily by the caller

ENDPOINT = "tcp/127.0.0.1:7447"


def _payload_bytes(sample) -> bytes:
    p = sample.payload
    for attr in ("to_bytes", "__bytes__"):
        if hasattr(p, attr):
            try:
                return bytes(getattr(p, attr)())
            except Exception:  # noqa: BLE001
                pass
    return bytes(p)


class ZenohBus:
    """A real-router transport with demo.InProcessBus's method shape. Bundles are
    retained by a memory storage the local-fabric router declares on keys/**, so a
    late reader's get() returns them — exactly as the production keys/** store does."""

    def __init__(self, endpoint: str = ENDPOINT) -> None:
        cfg = zenoh.Config.from_json5(json.dumps({
            "mode": "client",
            "connect": {"endpoints": [endpoint]},
            "scouting": {"multicast": {"enabled": False}},
        }))
        self._session = zenoh.open(cfg)
        self._subs = []            # keep subscriber handles alive
        time.sleep(0.5)            # let the client link to the router

    def put_key(self, topic: str, payload: bytes) -> None:
        self._session.put(topic, payload)

    def get_keys(self, prefix: str) -> list[tuple[str, bytes]]:
        out: list[tuple[str, bytes]] = []
        for reply in self._session.get(prefix + "**"):
            res = getattr(reply, "ok", None) or getattr(reply, "result", lambda: None)()
            sample = res if res is not None else getattr(reply, "sample", None)
            if sample is None:
                continue
            out.append((str(sample.key_expr), _payload_bytes(sample)))
        return sorted(out)

    def subscribe_data(self, prefix: str, cb: Callable[[str, bytes], None]) -> None:
        self._subs.append(self._session.declare_subscriber(
            prefix + "**" if prefix.endswith("/") else prefix,
            lambda s: cb(str(s.key_expr), _payload_bytes(s)),
        ))
        time.sleep(0.2)

    def put_data(self, topic: str, payload: bytes) -> None:
        self._session.put(topic, payload)
        time.sleep(0.3)            # allow delivery before the scenario checks results

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # noqa: BLE001
            pass
