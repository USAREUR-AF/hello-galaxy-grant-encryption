"""grant_enc — a readable reference of grant-keyed payload encryption.

READABLE TEACHING REFERENCE. This ~250-line module exists to be read top to
bottom: it is the clearest statement of the ONE mechanism the whole repo teaches.
Production producers and consumers do NOT use this file — they use the
grant-crypto SDK (the audited Rust core behind a versioned C ABI; ADR 1106), and
so do this repo's scenarios once you run `bin/fetch-sdk.sh`. This module and the
SDK are **wire-compatible by shared conformance vectors**: bytes sealed by one
open under the other, both directions (proven in `tests/cross_compat.py`). Keep it
as the reference; reach for the SDK to ship. See docs/honesty-matrix.md.

This is the ONE mechanism the whole repo teaches: how a data owner restricts a
stream to an audience by *encrypting to it*, on a brokerless fabric, with no
component decrypting in the read path. It mirrors the construction of the
production Rust core (`grant-crypto`, conformance-tested) closely enough to teach
every moving part; it is a pedagogical reimplementation, not the byte-for-byte
production library (see docs/honesty-matrix.md).

The shape, top to bottom:

  DEK          one AES-256-GCM data key per (release-set, generation).
               The stream is encrypted once with it — cost independent of
               audience size.
  Envelope     a sealed message: AES-256-GCM(dek, plaintext) with
               (suite, release-set, generation, topic) bound as AAD, so a
               message can only be opened for the exact stream + generation +
               topic it was sealed for.
  WrappedDek   the 32-byte DEK encrypted to ONE member's public key
               (ephemeral-static ECDH P-256 -> HKDF-SHA256 -> AES-256-GCM).
               N members -> N small wrapped copies, done per rotation only.
  KeyBundle    { member_id: WrappedDek, ... } published on keys/<rs>/<gen>,
               SIGNED by the key service so a member verifies authenticity
               before unwrapping. Everyone receives it; only a member opens a slot.

Read side: verify -> find your slot -> unwrap the DEK -> open the message.
An outsider has no slot, so the read is denied by the crypto, not by the router.
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SUITE_V1 = "v1-ecdh-p256"           # the crypto-agility id, bound into every AAD
DEK_WRAP_INFO = b"grant-crypto/dek-wrap/v1"
BUNDLE_SIG_DOMAIN = b"grant-crypto/bundle-sig/v1"
_CURVE = ec.SECP256R1()


class DeniedError(Exception):
    """Every failure is a *reject* — the read cut, surfaced as one exception."""


# ---- helpers: length-prefixed byte layouts (must be stable across languages) ----

def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)


def _lp(p: bytes) -> bytes:
    """8-byte big-endian length prefix + the bytes — the cross-language framing."""
    return struct.pack(">Q", len(p)) + p


def _sec1(pub: ec.EllipticCurvePublicKey) -> bytes:
    """Uncompressed SEC1 point — the fixed-length public-key wire form."""
    return pub.public_bytes(serialization.Encoding.X962,
                            serialization.PublicFormat.UncompressedPoint)


def _envelope_aad(suite: str, rs: str, gen: int, additional: bytes) -> bytes:
    # len8(suite)|suite | len8(rs)|rs | be64(gen) | additional  (the data topic)
    return _lp(suite.encode()) + _lp(rs.encode()) + struct.pack(">Q", gen) + additional


def _wrap_aad(suite: str, eph_pub: bytes, recipient_pub: bytes) -> bytes:
    # len8(suite)|suite | ephemeralPub | recipientPub  (points are fixed-length)
    return _lp(suite.encode()) + eph_pub + recipient_pub


# ---- wire structures ----

@dataclass
class Envelope:
    suite: str
    rs: str
    gen: int
    nonce: str  # b64
    ct: str     # b64

    def to_dict(self) -> dict:
        return {"suite": self.suite, "rs": self.rs, "gen": self.gen,
                "nonce": self.nonce, "ct": self.ct}

    @staticmethod
    def from_dict(d: dict) -> "Envelope":
        return Envelope(d["suite"], d["rs"], int(d["gen"]), d["nonce"], d["ct"])


@dataclass
class WrappedDek:
    suite: str
    epk: str    # b64 ephemeral public key (SEC1)
    nonce: str  # b64
    wct: str    # b64 wrapped-DEK ciphertext

    def to_dict(self) -> dict:
        return {"suite": self.suite, "epk": self.epk, "nonce": self.nonce, "wct": self.wct}

    @staticmethod
    def from_dict(d: dict) -> "WrappedDek":
        return WrappedDek(d["suite"], d["epk"], d["nonce"], d["wct"])


@dataclass
class KeyBundle:
    suite: str
    rs: str
    gen: int
    members: dict          # member_id -> WrappedDek
    signer: str = ""
    sig: str = ""          # b64 DER ECDSA signature over the transcript

    def to_dict(self) -> dict:
        return {"suite": self.suite, "rs": self.rs, "gen": self.gen,
                "members": {k: v.to_dict() for k, v in self.members.items()},
                "signer": self.signer, "sig": self.sig}

    @staticmethod
    def from_dict(d: dict) -> "KeyBundle":
        return KeyBundle(d["suite"], d["rs"], int(d["gen"]),
                         {k: WrappedDek.from_dict(v) for k, v in d["members"].items()},
                         d.get("signer", ""), d.get("sig", ""))


# ---- write side (producer + key service) ----

def new_dek() -> bytes:
    """A fresh random 256-bit DEK from the system CSPRNG."""
    import os
    return os.urandom(32)


def seal_envelope(dek: bytes, rs: str, gen: int, plaintext: bytes, keyexpr: str) -> Envelope:
    """Encrypt a payload under `dek`, binding (suite, rs, gen, keyexpr) as AAD so a
    stale-generation key or a cross-topic replay fails cleanly — the revocation lever."""
    import os
    aad = _envelope_aad(SUITE_V1, rs, gen, keyexpr.encode())
    nonce = os.urandom(12)
    ct = AESGCM(dek).encrypt(nonce, plaintext, aad)
    return Envelope(SUITE_V1, rs, gen, _b64e(nonce), _b64e(ct))


def wrap_dek(dek: bytes, recipient_pub: ec.EllipticCurvePublicKey) -> WrappedDek:
    """Wrap the DEK to one recipient: ephemeral-static ECDH P-256 -> HKDF-SHA256 ->
    AES-256-GCM, with the suite + both public keys bound as AAD."""
    import os
    eph = ec.generate_private_key(_CURVE)
    shared = eph.exchange(ec.ECDH(), recipient_pub)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=DEK_WRAP_INFO).derive(shared)
    eph_pub = _sec1(eph.public_key())
    aad = _wrap_aad(SUITE_V1, eph_pub, _sec1(recipient_pub))
    nonce = os.urandom(12)
    wct = AESGCM(kek).encrypt(nonce, dek, aad)
    return WrappedDek(SUITE_V1, _b64e(eph_pub), _b64e(nonce), _b64e(wct))


def new_bundle(rs: str, gen: int, dek: bytes, recipients: dict) -> KeyBundle:
    """Build a bundle by wrapping `dek` to each recipient (member_id -> public key).
    Fail-closed: order the members so the signed transcript is deterministic."""
    members = {mid: wrap_dek(dek, pub) for mid, pub in recipients.items()}
    return KeyBundle(SUITE_V1, rs, gen, members)


def _bundle_transcript(b: KeyBundle) -> bytes:
    out = _lp(BUNDLE_SIG_DOMAIN) + _lp(b.suite.encode()) + _lp(b.rs.encode())
    out += struct.pack(">Q", b.gen) + _lp(b.signer.encode())
    out += struct.pack(">Q", len(b.members))
    for mid in sorted(b.members):        # ascending id order == the Rust BTreeMap order
        w = b.members[mid]
        out += _lp(mid.encode()) + _lp(w.suite.encode())
        out += _lp(_b64d(w.epk)) + _lp(_b64d(w.nonce)) + _lp(_b64d(w.wct))
    return out


def sign_bundle(b: KeyBundle, signer: str, signing_key: ec.EllipticCurvePrivateKey) -> None:
    """Sign a bundle in place (ECDSA-P256/SHA-256). Members verify before unwrapping,
    so a bundle from anyone but the trusted key service is rejected."""
    b.signer = signer
    b.sig = ""
    sig = signing_key.sign(_bundle_transcript(b), ec.ECDSA(hashes.SHA256()))
    b.sig = _b64e(sig)


# ---- read side (member consumer) ----

def verify_bundle(b: KeyBundle, verifying_key: ec.EllipticCurvePublicKey) -> None:
    """Verify the bundle signature against the trusted key-service key. Raises on any
    tamper anywhere in the bundle (the signature covers the whole transcript)."""
    if not b.sig:
        raise DeniedError("bundle is unsigned")
    try:
        verifying_key.verify(_b64d(b.sig), _bundle_transcript(b), ec.ECDSA(hashes.SHA256()))
    except Exception as e:  # noqa: BLE001 — every failure is one reject
        raise DeniedError(f"bad bundle signature: {e}") from None


def unwrap_dek(w: WrappedDek, member_secret: ec.EllipticCurvePrivateKey) -> bytes:
    """Recover the DEK from this member's wrapped slot using the member's private key."""
    if w.suite != SUITE_V1:
        raise DeniedError(f"unsupported suite {w.suite!r}")
    eph_pub = ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, _b64d(w.epk))
    shared = member_secret.exchange(ec.ECDH(), eph_pub)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=DEK_WRAP_INFO).derive(shared)
    recipient_pub = _sec1(member_secret.public_key())
    aad = _wrap_aad(w.suite, _b64d(w.epk), recipient_pub)
    try:
        return AESGCM(kek).decrypt(_b64d(w.nonce), _b64d(w.wct), aad)
    except Exception:  # noqa: BLE001
        raise DeniedError("could not unwrap the DEK") from None


def open_envelope(dek: bytes, env: Envelope, keyexpr: str) -> bytes:
    """Open a sealed payload with the DEK, binding the data topic as AAD."""
    if env.suite != SUITE_V1:
        raise DeniedError(f"unsupported suite {env.suite!r}")
    aad = _envelope_aad(env.suite, env.rs, env.gen, keyexpr.encode())
    try:
        return AESGCM(dek).decrypt(_b64d(env.nonce), _b64d(env.ct), aad)
    except Exception:  # noqa: BLE001
        raise DeniedError("could not open the message (wrong key/generation/topic)") from None


def consume(b: KeyBundle, env: Envelope, member_id: str,
            member_secret: ec.EllipticCurvePrivateKey,
            verify_key: Optional[ec.EllipticCurvePublicKey], keyexpr: str) -> bytes:
    """The full member read path, in the required order:
    verify (if a trust key is given) -> find slot -> unwrap -> open."""
    if verify_key is not None:
        verify_bundle(b, verify_key)
    if member_id not in b.members:
        raise DeniedError(f"no slot for {member_id!r} — not in the audience")
    dek = unwrap_dek(b.members[member_id], member_secret)
    return open_envelope(dek, env, keyexpr)


# ---- identity helpers (each member/machine holds its OWN keypair) ----

@dataclass
class Identity:
    """A member's own keypair — the per-individual key the model requires (never a
    shared org key). `member_id` is the write-anchor/CN the DEK is wrapped under."""
    member_id: str
    key: ec.EllipticCurvePrivateKey = field(default_factory=lambda: ec.generate_private_key(_CURVE))

    @property
    def public(self) -> ec.EllipticCurvePublicKey:
        return self.key.public_key()

    @property
    def scalar(self) -> bytes:
        """The raw 32-byte P-256 private scalar — the exact key material the
        grant-crypto SDK's Identity is constructed from. Same scalar -> same
        public key, so the two interoperate on one bundle."""
        return self.key.private_numbers().private_value.to_bytes(32, "big")

    @classmethod
    def from_scalar(cls, member_id: str, scalar: bytes) -> "Identity":
        """Build an Identity from a raw 32-byte scalar (the enrollment key material),
        rather than generating a fresh one — the bridge to the SDK's key input."""
        key = ec.derive_private_key(int.from_bytes(scalar, "big"), _CURVE)
        return cls(member_id, key)
