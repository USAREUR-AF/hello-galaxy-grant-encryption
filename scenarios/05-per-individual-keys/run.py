#!/usr/bin/env python3
"""Scenario 05 — why keys are per-individual, and the org is only the grouping.

A tempting shortcut is "one key per organization, copied to its members." This
scenario shows, concretely, why that breaks — and why the design keeps a key per
individual with the organization as the authority/addressing unit, not a shared
secret. It contrasts the two head to head on the operation that matters:
removing one member.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import grant_enc as g          # noqa: E402
import demo as d               # noqa: E402
import narrate as n            # noqa: E402
import sdk_bridge as sdk       # noqa: E402


def main() -> None:
    n.banner("05 — Per-individual keys", "the org is the grouping unit, never a shared key")
    n.honest(f"endpoint crypto backend: {sdk.backend_name()}")

    rs = "weather-feed"
    ks = d.KeyService(g.Identity("site-a/key-service"))
    bus = d.InProcessBus()
    prod = g.Identity(f"{rs}/prod")

    n.step("The shortcut: ONE org keypair, every member holds a copy. Remove one member —")
    n.say("… and the removed member still holds the org's private key. To actually cut it off you")
    n.say("must mint a NEW org keypair and redistribute it to EVERY remaining member, then re-wrap.")
    n.say("One departure => an org-wide key ceremony. And no per-member attribution: everyone is")
    n.say("cryptographically identical, so a leak can't be traced to a person.")
    n.deny("shared org key: revoking one member forces a whole-org re-key + redistribution.")

    n.step("The design: each member holds its OWN keypair; the org is only how we group + address them.")
    a = g.Identity(f"{rs}/a"); b = g.Identity(f"{rs}/b"); c = g.Identity(f"{rs}/c")
    ks.rotate(bus, prod.member_id, {prod.member_id: prod.public,
                                    a.member_id: a.public, b.member_id: b.public, c.member_id: c.public})
    n.say("gen 1 wraps to {prod, a, b, c} — four independent keys, none shared.")

    n.step("Remove c: mint gen 2 to {prod, a, b}. No one else is touched, no secret redistributed.")
    ks.rotate(bus, prod.member_id, {prod.member_id: prod.public, a.member_id: a.public, b.member_id: b.public})
    reader_a = d.Consumer(a, prod.member_id, ks.verifying_key); held_a = reader_a.refresh_keys(bus)
    reader_c = d.Consumer(c, prod.member_id, ks.verifying_key); held_c = reader_c.refresh_keys(bus)
    n.ok(f"a still holds current keys ({held_a} generations); nobody re-keyed a, b or prod.")
    n.deny(f"c holds only gen 1 ({held_c} generation); it is simply absent from gen 2.")

    n.step("Two dials, set separately by the owner.")
    n.say("• REACH — where the stream is published (which channel) — decides who receives the bytes.")
    n.say("• READABILITY — who holds the key — decides who can open them. They combine freely.")

    n.step("What it proves.")
    n.say("• Per-individual keys give granular revocation (drop one slot), per-member attribution, and no shared secret to distribute.")
    n.say("• A shared org key would trade all three away for a smaller bundle — a bad trade this design refuses.")
    n.honest("When a flat audience grows past comfort, the scale answer is a key tree (MLS/TreeKEM) — the "
             "group-key idea done properly, with forward secrecy — NOT a static shared key.")

    n.result(held_a == 2 and held_c == 1,
             "removing one member touched only that member; every key stayed per-individual.")


if __name__ == "__main__":
    main()
