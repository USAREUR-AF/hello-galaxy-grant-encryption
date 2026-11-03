#!/usr/bin/env python3
"""Scenario 06 — "who could decrypt this?", asked BEFORE publishing.

Scenario 02 showed the audience being derived from a grant. This is the question
a producer actually asks at the moment of publishing: not *who is the audience*
as a list of anchors, but *is my restriction set right* — answered fast enough
to be a gut check.

Two things make it more than a count.

The rule is an INTERSECTION (ADR 1171). Being in the grantee org is not enough:
the holder's own nationality must also be one of the nations that own that org.
Two people at the same desk, separated by citizenship and nothing else.

And the answer distinguishes EXCLUDED from UNDECLARED. Both are zero and they
mean opposite things — the restriction holding, versus a registry nobody filled
in. A producer who reads the second as the first concludes the sharing is locked
down when the question was never answerable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import grant_enc as g          # noqa: E402
import demo as d               # noqa: E402
import narrate as n            # noqa: E402

# The nations in this scenario are invented: Ardenia (ARD), Borealia (BOR),
# Calvaria (CAL), Dovania (DOV), Fenmark (FEN). COMPACT is an invented alliance
# whose member nations own the multinational org below.
COMPACT = {"ARD", "BOR", "CAL", "FEN"}

def _render(p: dict) -> None:
    """Print the preview the way the portal returns it — counts only."""
    n.say(f"  encrypted   {str(p['encrypted']).lower()}")
    n.say(f"  holders     {p['holders']}")
    n.say(f"  evaluable   {str(p['evaluable']).lower()}")
    for label, key in (("nationality", "by_nationality"), ("org", "by_org")):
        cells = p[key]
        if not cells:
            n.say(f"  by {label:<9} -")
            continue
        for c in cells:
            if c.get("withheld"):
                n.say(f"  by {label:<9} [withheld: {c['holders']} holder(s) across {c['cells']} cell(s)]")
            else:
                n.say(f"  by {label:<9} {c['value']}: {c['holders']}")
    r = p["refused"]
    n.say(f"  refused     excluded={r[d.EXCLUDED]}  "
          f"org-nation-undeclared={r[d.ORG_NATION_UNDECLARED]}  "
          f"holder-nationality-undeclared={r[d.HOLDER_NATIONALITY_UNDECLARED]}")


def main() -> None:
    n.banner("06 - Who could decrypt this?",
             "the producer's pre-publish gut check, and why a zero is not one answer")

    n.step("An Ardenian-owned organisation. Three people at the same desk, three different facts.")
    roster = d.Roster()
    roster.declare_org("acme-sensors", nation="FEN", composition="national")
    roster.declare_org("ardenia-ops", nation="ARD", composition="national")
    K = roster.add_machine("acme-sensors", g.Identity("acme-sensors/sensor-k"), nationality="FEN").member_id
    ard = roster.add_machine("ardenia-ops", g.Identity("ardenia-ops/analyst-ard"), nationality="ARD").member_id
    bor = roster.add_machine("ardenia-ops", g.Identity("ardenia-ops/analyst-bor"), nationality="BOR").member_id
    un = roster.add_machine("ardenia-ops", g.Identity("ardenia-ops/analyst-un")).member_id
    n.say("org ardenia-ops   nation=ARD  composition=national")
    n.say(f"  {ard}   nationality ARD")
    n.say(f"  {bor}   nationality BOR   (a full member - 'assigned', not a liaison)")
    n.say(f"  {un}   nationality UNDECLARED")

    n.step("The owner records ONE grant: share producer K with org ardenia-ops.")
    grants = [d.Grant(producer=K, grantee_kind="org", grantee_id="ardenia-ops",
                      justification="shared weather picture")]

    n.step("Before encrypting, the producer asks who could decrypt it.")
    _render(d.preview_audience(K, grants, roster, COMPACT))

    n.ok("1 holder. The Ardenian is in; the Borealian at the same desk is not.")
    n.honest("`relationship` is deliberately not consulted. Testing it instead would "
             "exclude the Ardenian too - ADR 1171 makes them both `assigned` - and "
             "empty the organisation.")
    n.honest("The undeclared holder is refused as well: absence is not a match, and a "
             "guess here would be a silent disclosure.")
    n.honest("Nothing above names anybody. The breakdown is withheld because 1 holder is "
             f"below the k-anonymity floor of {d.K_ANONYMITY_FLOOR} - "
             "\"1 holder, ARD, ardenia-ops\" is a name to anyone who knows the org.")

    n.step("Now the case that makes this surface worth having: an org that declared nothing.")
    roster2 = d.Roster()
    roster2.declare_org("acme-sensors", nation="FEN", composition="national")
    K2 = roster2.add_machine("acme-sensors", g.Identity("acme-sensors/sensor-k2"), nationality="FEN").member_id
    for i in range(3):
        roster2.add_machine("newpartner", g.Identity(f"newpartner/node-{i}"), nationality="CAL")
    grants2 = [d.Grant(producer=K2, grantee_kind="org", grantee_id="newpartner")]
    _render(d.preview_audience(K2, grants2, roster2, COMPACT))

    n.deny("0 holders - and this zero is NOT the same zero as a tight restriction.")
    n.honest("evaluable=false. Nobody could be tested, because the organisation never "
             "declared an owning nation. Read as 'nobody qualifies' it says the sharing is "
             "locked down; it actually says the question is unanswerable.")
    n.honest("A registry where many organisations have not yet declared an owning nation "
             "would otherwise show a bare zero that reads as 'tightly restricted'.")

    n.step("A multinational org: owned by a body, so the nations that own it are the body's.")
    roster3 = d.Roster()
    roster3.declare_org("acme-sensors", nation="FEN", composition="national")
    roster3.declare_org("compact-hq", nation="COMPACT", composition="multinational")
    K3 = roster3.add_machine("acme-sensors", g.Identity("acme-sensors/sensor-k3"), nationality="FEN").member_id
    roster3.add_machine("compact-hq", g.Identity("compact-hq/ard"), nationality="ARD")
    roster3.add_machine("compact-hq", g.Identity("compact-hq/cal"), nationality="CAL")
    roster3.add_machine("compact-hq", g.Identity("compact-hq/dov"), nationality="DOV")
    grants3 = [d.Grant(producer=K3, grantee_kind="org", grantee_id="compact-hq")]
    _render(d.preview_audience(K3, grants3, roster3, COMPACT))

    n.ok("2 holders: the Ardenian and the Calvarian. The Dovanian in the same organisation is not.")
    n.honest("A person's nationality can never equal the marker 'COMPACT', so testing the "
             "marker as a nation would admit nobody and empty every multinational org. An "
             "ownership class whose audience is always empty is a defect, not a policy - so "
             "`multinational` admits the body's member nations.")

    n.step("Access and decryption disagree here, by design.")
    n.honest("The Borealian and the Dovanian hold their organisation's READ access. They see "
             "that the stream exists and cannot open its payload. That split is the point of "
             "encrypting to an audience - but unannounced it is indistinguishable from a "
             "fault, which is this fabric's existing silent-denial problem. The "
             "preview is where it becomes visible BEFORE it becomes a support ticket.")

    n.step("Two limits the preview states rather than hides.")
    n.honest("Not every message is encrypted - the rule governs only payloads a publisher "
             "chose to wrap. A release-set with no grant reports encrypted=false and has no "
             "audience to preview.")
    n.honest("A publisher may widen a specific grant deliberately. The preview shows the "
             "rule's default, not a ceiling.")

    n.result(True, "the producer can see the shape of the audience, and tell an unanswerable "
                   "zero from a restrictive one, before publishing")


if __name__ == "__main__":
    main()
