#!/usr/bin/env python3
"""Scenario 03 — read and deny, over the fabric.

The whole apparatus, end to end, on a pub/sub bus: the key service publishes a
signed bundle; the producer (a member) fetches it, unwraps its own slot, seals a
stream, and publishes ciphertext; a member consumer opens it; an OUTSIDER
subscribes the same topic, receives the identical bytes, and cannot open them.
The read cut is enforced by the crypto — the bus routes ciphertext it cannot read.

Runs on an in-process bus by default (zero dependencies). Pass --fabric to carry
the identical bytes over a real eclipse/zenoh router (see local-fabric/README.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import grant_enc as g          # noqa: E402
import demo as d               # noqa: E402
import narrate as n            # noqa: E402
import sdk_bridge as sdk       # noqa: E402


def main() -> None:
    fabric = "--fabric" in sys.argv
    n.banner("03 — Read and deny", "producer seals -> member opens -> outsider denied, over the bus")
    n.honest(f"endpoint crypto backend: {sdk.backend_name()}")

    rs = "weather-feed"
    roster = d.Roster()
    producer = roster.add_machine("acme-sensors", g.Identity(f"{rs}/prod"))
    member = roster.add_machine("northwind", g.Identity(f"{rs}/con"))
    outsider = g.Identity("outsider/eve")            # a valid fabric identity, NOT in the audience

    n.step("The data owner grants the stream to org northwind; the key service derives the audience + publishes the bundle.")
    grants = [d.Grant(producer=producer.member_id, grantee_kind="org", grantee_id="northwind")]
    audience, _ = d.derive_audience(producer.member_id, grants, roster)
    ks = d.KeyService(g.Identity("site-a/key-service"))

    if fabric:
        n.honest("--fabric: this path needs docker + `pip install eclipse-zenoh` (see local-fabric/). "
                 "Falling through to the in-process bus if the import fails.")
        try:
            from zenoh_bus import ZenohBus  # type: ignore
            bus = ZenohBus()
        except Exception as e:  # noqa: BLE001
            n.honest(f"eclipse-zenoh not available ({e}); using the in-process bus.")
            bus = d.InProcessBus()
    else:
        bus = d.InProcessBus()

    gen = ks.rotate(bus, producer.member_id, audience)
    n.ok(f"key service published keys/{producer.member_id}/{gen} to {len(audience)} members.")

    n.step("A member consumer and an OUTSIDER both subscribe the data topic — same subscription, same bytes.")
    topic = f"data/{producer.member_id}/obs"
    con = d.Consumer(member, producer.member_id, ks.verifying_key)
    eve = d.Consumer(outsider, producer.member_id, ks.verifying_key)
    con.refresh_keys(bus)      # the member holds a slot
    eve.refresh_keys(bus)      # the outsider holds none
    bus.subscribe_data(topic, con.on_message)
    bus.subscribe_data(topic, eve.on_message)
    n.say(f"member holds {len(con._deks)} key(s); outsider holds {len(eve._deks)} key(s).")

    n.step("The producer unwraps ITS OWN slot for the DEK and publishes a sealed message.")
    plaintext = b"STATION 7: wind 040 at 12 kt"
    prod = d.Producer(producer, producer.member_id)
    prod.publish(bus, topic, plaintext)
    n.say(f"published ciphertext on {topic}.")

    n.step("The member opens it; the outsider — handed the identical bytes — cannot.")
    for t, gn, pt in con.opened:
        n.ok(f"member opened gen {gn}: {pt.decode()}")
    if eve.opened:
        n.deny("outsider OPENED the message — this must never happen")
    for t, gn in eve.denied:
        n.deny(f"outsider denied on gen {gn} (no slot) — the read cut, by the crypto")

    n.step("What it proves.")
    n.say("• Producer-as-member: the producer needs no separate key channel — it opens its own slot.")
    n.say("• The bus broadcasts ciphertext; membership, not the router, decides who can read.")
    n.say("• The outsider is a fully-enrolled fabric identity — enrolment is not read authorization.")
    n.honest("Default run uses an in-process bus modelling Zenoh pub/sub. --fabric carries the same bytes over a real router.")

    ok = (len(con.opened) == 1 and con.opened[0][2] == plaintext
          and not eve.opened and len(eve.denied) == 1)
    n.result(ok, "the member read the stream; the outsider received it and could not open it.")


if __name__ == "__main__":
    main()
