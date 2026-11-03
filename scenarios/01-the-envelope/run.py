#!/usr/bin/env python3
"""Scenario 01 — the envelope: one key seals the stream, a member opens it.

The single idea everything else rests on. Encrypt the payload ONCE with a
symmetric data key (the DEK); wrap that DEK to each member's public key. The
per-message cost is one AES-GCM seal, independent of how many members there are.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import json                    # noqa: E402
import grant_enc as g          # noqa: E402
import narrate as n            # noqa: E402
import sdk_bridge as sdk       # noqa: E402


def main() -> None:
    n.banner("01 — The envelope", "one DEK seals the stream; the DEK is wrapped to each member")
    n.honest("this scenario reads the reference (lib/grant_enc.py) to teach the internals; "
             "scenarios 03-05 run the endpoint crypto on the production SDK when present.")

    n.step("The key service mints ONE data key (DEK) for release-set 'weather-feed', generation 1.")
    ks = g.Identity("key-service")
    dek = g.new_dek()
    n.say(f"DEK = {len(dek)*8}-bit AES-256 key (held only long enough to wrap it).")

    n.step("Two members each hold their OWN keypair. The DEK is wrapped to each — N members, N small copies.")
    alice = g.Identity("weather-feed/alice")
    bravo = g.Identity("weather-feed/bravo")
    bundle = g.new_bundle("weather-feed", 1, dek, {alice.member_id: alice.public,
                                                    bravo.member_id: bravo.public})
    g.sign_bundle(bundle, ks.member_id, ks.key)
    n.say(f"bundle keys/weather-feed/1 has {len(bundle.members)} wrapped slots, signed by {bundle.signer!r}.")

    n.step("A producer seals a message with the DEK — once, regardless of audience size.")
    msg = b"STATION 7: wind 040 at 12 kt, visibility 10 km"
    env = g.seal_envelope(dek, "weather-feed", 1, msg, "data/weather-feed/obs")
    n.say(f"ciphertext = {len(g._b64d(env.ct))} bytes on topic data/weather-feed/obs.")

    n.step("A member verifies the bundle, unwraps ITS slot, and opens the message.")
    opened = g.consume(bundle, env, bravo.member_id, bravo.key, ks.key.public_key(), "data/weather-feed/obs")
    n.ok(f"member 'bravo' read: {opened.decode()}")

    sdk_cross_ok = None
    if sdk.available():
        n.step("Same wire, two libraries: the production SDK opens the bytes grant_enc sealed — and the reverse.")
        keyexpr = "data/weather-feed/obs"
        bundle_json = json.dumps(bundle.to_dict()).encode()
        # forward: grant_enc sealed `env` above; the SDK verifies + admits + opens it.
        with sdk.gc.Identity(bravo.member_id, sdk.scalar_of(bravo)) as sid, sdk.gc.KeyStore() as store:
            sdk.gc.verify_bundle(bundle_json, sdk.spki_der(ks.key.public_key()))
            store.admit(sid, bundle_json)
            sdk_read = store.open(keyexpr, json.dumps(env.to_dict()).encode())
        n.ok(f"SDK opened grant_enc's ciphertext: {sdk_read.decode()}")
        # reverse: the SDK seals under the same bundle; grant_enc unwraps + opens it.
        with sdk.gc.Identity(bravo.member_id, sdk.scalar_of(bravo)) as sid:
            with sdk.gc.StreamKey.acquire(json.dumps([bundle.to_dict()]).encode(), "weather-feed", sid) as sk:
                sdk_env = sk.seal(keyexpr, b"sealed by the SDK, opened by the reference")
        ge_dek = g.unwrap_dek(bundle.members[bravo.member_id], bravo.key)
        ge_read = g.open_envelope(ge_dek, g.Envelope.from_dict(json.loads(sdk_env)), keyexpr)
        n.ok(f"grant_enc opened the SDK's ciphertext: {ge_read.decode()}")
        sdk_cross_ok = (sdk_read == msg and ge_read == b"sealed by the SDK, opened by the reference")
    else:
        n.honest("the SDK is not materialized (run bin/fetch-sdk.sh) — skipping the cross-library wire check.")

    n.step("What it proves.")
    n.say("• The payload is encrypted once; adding members costs one small wrapped-key copy each, not a re-encrypt.")
    n.say("• The bundle is authenticated — a member verifies the key service's signature BEFORE unwrapping.")
    n.say("• The AAD binds (suite, release-set, generation, topic): a message can only open for exactly what it was sealed for.")
    n.honest("Pure crypto here — no fabric yet. Scenario 03 carries the same bytes over a real router.")
    if sdk_cross_ok is not None:
        n.say("• The reference and the production SDK are wire-compatible — same envelope + bundle format, both directions.")

    assert opened == msg
    assert sdk_cross_ok is None or sdk_cross_ok, "SDK <-> grant_enc wire cross-check failed"
    n.result(True, "one DEK sealed the stream; the authorized member opened it.")


if __name__ == "__main__":
    main()
