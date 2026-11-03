#!/usr/bin/env python3
"""Scenario 04 — revocation is rotation.

There is no "delete key" step. To remove a member you mint the NEXT generation
without it: the new bundle wraps the new DEK to everyone else. The removed member
keeps whatever generations it already held (bytes can't be clawed back) but gets
nothing new. The generation label carries revocation — no flag-day, no re-encrypt
of the audience.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import grant_enc as g          # noqa: E402
import demo as d               # noqa: E402
import narrate as n            # noqa: E402
import sdk_bridge as sdk       # noqa: E402


def main() -> None:
    n.banner("04 — Revocation is rotation", "remove a member -> next generation excludes it")
    n.honest(f"endpoint crypto backend: {sdk.backend_name()}")

    rs = "weather-feed"
    roster = d.Roster()
    prod = roster.add_machine("acme-sensors", g.Identity(f"{rs}/prod"))
    a = roster.add_machine("northwind", g.Identity(f"{rs}/a"))
    b = roster.add_machine("northwind", g.Identity(f"{rs}/b"))
    ks = d.KeyService(g.Identity("site-a/key-service"))
    bus = d.InProcessBus()
    topic = f"data/{prod.member_id}/obs"

    n.step("Generation 1: audience {prod, a, b}. Both a and b can read.")
    aud1 = {prod.member_id: prod.public, a.member_id: a.public, b.member_id: b.public}
    ks.rotate(bus, prod.member_id, aud1)
    producer = d.Producer(prod, prod.member_id)
    reader_a = d.Consumer(a, prod.member_id, ks.verifying_key); reader_a.refresh_keys(bus)
    reader_b = d.Consumer(b, prod.member_id, ks.verifying_key); reader_b.refresh_keys(bus)
    bus.subscribe_data(topic, reader_a.on_message)
    bus.subscribe_data(topic, reader_b.on_message)
    producer.publish(bus, topic, b"gen-1: both of you can read this")
    n.ok(f"a opened gen {reader_a.opened[-1][1]}; b opened gen {reader_b.opened[-1][1]}")

    n.step("The data owner revokes b. The key service rotates to generation 2 with audience {prod, a}.")
    aud2 = {prod.member_id: prod.public, a.member_id: a.public}   # b excluded
    ks.rotate(bus, prod.member_id, aud2)
    reader_a.refresh_keys(bus)      # a admits gen 2
    held_b = reader_b.refresh_keys(bus)  # b finds no gen-2 slot
    n.say(f"after rotation: a holds {len(reader_a._deks)} generations; b still holds {held_b} (gen 1 only).")

    n.step("The producer publishes a generation-2 message.")
    producer.publish(bus, topic, b"gen-2: only current members can read this")

    n.step("a reads gen 2; b is denied gen 2 but its gen-1 reads still stand.")
    a_read_gen2 = any(gn == 2 for _, gn, _ in reader_a.opened)
    b_denied_gen2 = any(gn == 2 for _, gn in reader_b.denied)
    b_kept_gen1 = any(gn == 1 for _, gn, _ in reader_b.opened)
    if a_read_gen2:
        n.ok("a (still a member) opened the generation-2 message")
    if b_denied_gen2:
        n.deny("b (revoked) cannot open the generation-2 message — no gen-2 slot")
    if b_kept_gen1:
        n.say("b keeps its earlier generation-1 read (bytes already delivered are not clawed back)")

    n.step("What it proves.")
    n.say("• Revocation = a new generation that omits the member; no key-deletion, no flag-day.")
    n.say("• The generation tag on each message routes it to the right key; readers switch lazily.")
    n.say("• The instant hard cut still lives one layer down (revoke the cert -> off the fabric in seconds); this is the finer 'stays on the fabric, loses this stream' case.")
    n.honest("Forward secrecy for prior generations is out of scope here; MLS/TreeKEM is the strategic path (see docs).")

    n.result(a_read_gen2 and b_denied_gen2 and b_kept_gen1,
             "the revoked member lost the next generation and kept only what it already held.")


if __name__ == "__main__":
    main()
