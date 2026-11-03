"""sdk_bridge — run the demo's producer + consumer on the PRODUCTION grant-crypto SDK.

The rest of the repo is the readable reference (`lib/grant_enc.py`) plus the
system shape (`lib/demo.py`). This module is the seam that swaps the *endpoint*
crypto — the producer's `seal` and the consumer's `verify → admit → open` — onto
the real grant-crypto SDK when it is present under `./sdk/` (materialized by
`bin/fetch-sdk.sh`). That SDK is the exact library production producers and
consumers use: a Rust core behind a versioned C ABI, with a stdlib-only Python
binding. `grant_enc` stays as the teaching reference and, when the SDK is absent,
as the fallback so a bare clone still runs top to bottom.

What crosses this seam matches the SDK's own boundary contract: only wire bytes
(bundle / envelope JSON) and a member's raw 32-byte scalar — never a DEK. The key
SERVICE (mint → wrap → sign) is deliberately NOT here: the SDK exposes no
key-authority surface (a producer is not a key authority), so the demo's key
service stays on `grant_enc`, mirroring the real `grant-keyd` daemon. A bundle the
`grant_enc` key service signs is verified, admitted, and opened by the SDK here —
so simply running a scenario already crosses the reference→SDK wire boundary.
"""
from __future__ import annotations

import atexit
import json
import sys
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization

import grant_enc as g

_SDK_PY = Path(__file__).resolve().parents[1] / "sdk" / "bindings" / "python"

gc = None  # the grant_crypto module, or None when the SDK is not materialized
try:
    if _SDK_PY.is_dir():
        sys.path.insert(0, str(_SDK_PY))
    import grant_crypto as _gc  # noqa: E402  (optional; guarded)

    gc = _gc
except Exception:  # noqa: BLE001 — any import/load failure means "run the reference"
    gc = None


def available() -> bool:
    """True when the production SDK is materialized and its C ABI loaded."""
    return gc is not None


def backend_name() -> str:
    return "grant-crypto SDK (production, C ABI v%d)" % gc.abi_version() if gc else \
        "grant_enc reference (lib/grant_enc.py) — run bin/fetch-sdk.sh for the real SDK"


# ---- small conversions between the reference's key objects and the SDK's inputs ----

def scalar_of(identity: g.Identity) -> bytes:
    """The member's raw 32-byte P-256 scalar — the exact key material the SDK's
    Identity consumes. The reference and the SDK derive the SAME public key from
    it, so a bundle wrapped to `identity.public` opens under the SDK identity."""
    return identity.key.private_numbers().private_value.to_bytes(32, "big")


def spki_der(public_key) -> bytes:
    """A verifying key as SPKI DER — the form the SDK's `verify_bundle` expects."""
    return public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


# ---- the two endpoint roles, on the SDK ----

class SdkProducer:
    """A producer that seals on the SDK: acquire a stream key from its own bundle
    slot (highest visible generation of the release-set), then seal — no recipients,
    no nonce, no algorithm at the call site (the SDK supplies them)."""

    def __init__(self, identity: g.Identity, rs: str):
        self._id = gc.Identity(identity.member_id, scalar_of(identity))
        self._rs = rs
        atexit.register(self.close)

    def seal(self, bundles: list[dict], keyexpr: str, plaintext: bytes) -> tuple[int, bytes]:
        """Returns (generation, envelope_json_bytes). `bundles` is every key bundle
        for the release-set currently on the bus."""
        bundles_json = json.dumps(bundles).encode()
        with gc.StreamKey.acquire(bundles_json, self._rs, self._id) as sk:
            env = sk.seal(keyexpr, plaintext)
        return json.loads(env)["gen"], env

    def close(self) -> None:
        if getattr(self, "_id", None) is not None:
            self._id.close()
            self._id = None


class SdkConsumer:
    """A consumer that reads on the SDK: verify each bundle against the key
    service's verifying key, admit its own slot (retaining the DEK), and open data
    messages. An outsider admits nothing and every open fails closed."""

    def __init__(self, identity: g.Identity, vk_spki: bytes):
        self._id = gc.Identity(identity.member_id, scalar_of(identity))
        self._store = gc.KeyStore()
        self._vk = vk_spki
        atexit.register(self.close)

    def admit(self, bundle: dict) -> bool:
        """Verify (authenticity) then admit (unwrap our slot). Returns True if we
        held a slot for this generation, False for an outsider — a normal
        fail-closed outcome, not an error."""
        bundle_json = json.dumps(bundle).encode()
        gc.verify_bundle(bundle_json, self._vk)      # reject a bundle not from the key service
        return self._store.admit(self._id, bundle_json)

    def open(self, keyexpr: str, envelope: dict) -> bytes:
        """Open a data message with the held DEK; raises `grant_enc.DeniedError`
        (the demo's uniform reject) when there is no slot or the AEAD fails."""
        try:
            return self._store.open(keyexpr, json.dumps(envelope).encode())
        except (gc.NoSlotError, gc.DecryptError, gc.UnsupportedSuiteError) as e:
            raise g.DeniedError(str(e)) from None

    def close(self) -> None:
        if getattr(self, "_store", None) is not None:
            self._store.close()
            self._store = None
        if getattr(self, "_id", None) is not None:
            self._id.close()
            self._id = None
