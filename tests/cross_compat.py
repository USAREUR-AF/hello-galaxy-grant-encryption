#!/usr/bin/env python3
"""cross_compat — prove the reference and the production SDK share one wire format.

The claim the whole rebase rests on: `lib/grant_enc.py` (the readable reference)
and the grant-crypto SDK (the library production endpoints use) are byte-for-byte
wire-compatible. This asserts it directly, both directions, end to end:

  1. grant_enc seals  -> the SDK verifies + admits + opens.
  2. the SDK seals     -> grant_enc unwraps + opens.
  3. an outsider (valid identity, no slot) is denied by the SDK, fail-closed.

The key SERVICE (mint DEK -> wrap-to-each -> sign the bundle) is grant_enc in both
directions — that mirrors the real `grant-keyd` daemon, and the SDK deliberately
has no key-authority surface. So this also proves a grant_enc-signed bundle is
what the SDK authenticates and unwraps.

Exit 0 on success; exit 2 if the SDK is not materialized (run bin/fetch-sdk.sh);
non-zero on any mismatch. CI-runnable once the SDK is present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

import grant_enc as g          # noqa: E402
import sdk_bridge as sdk       # noqa: E402

RS = "weather-feed"
KEYEXPR = "data/weather-feed/obs"


def main() -> int:
    if not sdk.available():
        print("SKIP: the grant-crypto SDK is not materialized — run bin/fetch-sdk.sh", file=sys.stderr)
        return 2
    gc = sdk.gc
    print(f"backend: {sdk.backend_name()}")

    # --- key service (grant_enc): mint a DEK, wrap it to the member, sign the bundle ---
    ks = g.Identity("site-a/key-service")
    member = g.Identity(f"{RS}/con")
    outsider = g.Identity("outsider/eve")
    dek = g.new_dek()
    bundle = g.new_bundle(RS, 1, dek, {member.member_id: member.public})
    g.sign_bundle(bundle, ks.member_id, ks.key)
    bundle_json = json.dumps(bundle.to_dict()).encode()
    bundles_json = json.dumps([bundle.to_dict()]).encode()
    vk_spki = sdk.spki_der(ks.key.public_key())

    failures = []

    # 1) grant_enc seals -> SDK opens
    msg1 = b"sealed by grant_enc, opened by the SDK"
    env1 = g.seal_envelope(dek, RS, 1, msg1, KEYEXPR)
    with gc.Identity(member.member_id, sdk.scalar_of(member)) as sid, gc.KeyStore() as store:
        gc.verify_bundle(bundle_json, vk_spki)
        if not store.admit(sid, bundle_json):
            failures.append("SDK admit: member should have a slot")
        got1 = store.open(KEYEXPR, json.dumps(env1.to_dict()).encode())
    if got1 != msg1:
        failures.append(f"dir1 mismatch: {got1!r} != {msg1!r}")
    else:
        print("ok  grant_enc-seal -> SDK-open")

    # 2) SDK seals -> grant_enc opens
    msg2 = b"sealed by the SDK, opened by grant_enc"
    with gc.Identity(member.member_id, sdk.scalar_of(member)) as sid:
        with gc.StreamKey.acquire(bundles_json, RS, sid) as sk:
            env2_json = sk.seal(KEYEXPR, msg2)
    ge_dek = g.unwrap_dek(bundle.members[member.member_id], member.key)
    got2 = g.open_envelope(ge_dek, g.Envelope.from_dict(json.loads(env2_json)), KEYEXPR)
    if got2 != msg2:
        failures.append(f"dir2 mismatch: {got2!r} != {msg2!r}")
    else:
        print("ok  SDK-seal -> grant_enc-open")

    # 3) outsider denied by the SDK (no slot), fail-closed
    with gc.Identity(outsider.member_id, sdk.scalar_of(outsider)) as oid, gc.KeyStore() as store:
        gc.verify_bundle(bundle_json, vk_spki)
        if store.admit(oid, bundle_json):
            failures.append("outsider unexpectedly had a slot")
        try:
            store.open(KEYEXPR, json.dumps(env1.to_dict()).encode())
            failures.append("outsider opened the stream — must never happen")
        except gc.NoSlotError:
            print("ok  outsider denied by the SDK (NoSlot)")

    if failures:
        for f in failures:
            print("FAIL", f, file=sys.stderr)
        return 1
    print("PASS  reference and SDK are wire-compatible, both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
