"""Offline self-test of the YouTube and Gmail follow-the-pointer assessments, the Gmail privacy scan and the
driver's allowlist: a good walk passes every rule, a bad walk fails each rule it breaks. No screen, Safari, Sarvam.
Uses only fake addresses.

    .venv/bin/python scripts/qa/selftest_site_assess.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts", ROOT / "scripts" / "qa" / "checks"):
    sys.path.insert(0, str(p))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/qa/checks" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


yt, gm = load("youtube_follow_pointer_e2e"), load("gmail_follow_pointer_e2e")
X = Path("/tmp/x.jsonl")


def dec(i, phase, label, text, role="AXButton", kind="point", action="pressed", valid=True, **extra):
    rec = {"event": "decision", "index": i, "phase": phase, "kind": kind, "valid": valid, "instruction_en": text,
           "source": "sarvam", "action": action}
    if kind == "point":
        rec.update(target_label=label, target_role=role, times_pointed=1)
    return {**rec, **extra}


def statuses(got):
    return {r["check"][:60]: r["status"] for r in got if r["evidence"] != "needs-human"}


# ---------------------------------------------------------------- YouTube
LINK = "Darshana (Official Video) | Hridayam | Pranav"
DEC = "Decrease playback speed 0.05"


def reindex(recs):
    n = 0
    for r in recs:
        if r["event"] == "decision":
            r["index"], n = n, n + 1
    return recs


def q2(counts=(5, 4, 3, 2, 1), end="complete"):
    out = [dec(0, 2, "Settings", "Open 'Settings'.", "AXPopUpButton"),
           dec(0, 2, "Playback speed Normal", "Open 'Playback speed' to see the available speeds.", "AXMenuItem")]
    out += [dec(0, 2, DEC, f"Press − to slow down ({n} more times).", action="pressed") for n in counts]
    if end == "complete":
        out.append(dec(0, 2, None, "The video is set to 0.75×.", kind="complete", action="none"))
    return out


STOP_OK = {"event": "stop", "reason": "phase1=complete phase2=complete", "phases": {"1": "complete", "2": "complete"},
           "decreases": 5, "speed_restored": True, "menu_closed": True, "speed_after": 1.0}
Q1 = [
    dec(0, 1, "Search", "Type 'Darshana' in 'Search'.", "AXComboBox", action="typed (value not recorded)"),
    dec(0, 1, "Search", "Click 'Search' to see the results."),
    dec(0, 1, LINK, "Open the video to play it.", "AXLink", url_watch=True),
    dec(0, 1, None, "The video is playing.", kind="complete", action="none"),
    {"event": "state", "name": "after-find", "playing": True, "url_watch": True},
]
YGOOD = reindex(Q1 + q2() + [dict(STOP_OK)])
YBAD = reindex([  # Search button first, button pointed twice, an ad and an unrelated link, invalid pointer, no playing, speed never reached
    dec(0, 1, "Search", "Click Search.", "AXButton"),
    dec(0, 1, "Search", "Type here.", "AXComboBox"),
    dec(0, 1, "Search", "Click Search.", "AXButton", times_pointed=2),
    dec(0, 1, "Ad · Sponsored: Buy Now", "Open this.", "AXLink", url_watch=False),
    dec(0, 1, "Top 10 cooking videos", "Open this.", "AXLink", url_watch=True, valid=False),
    {"event": "state", "name": "after-find", "playing": False, "url_watch": False},
    dec(0, 2, "Playback speed Normal", "Open it.", "AXMenuItem"),
    dec(0, 2, "1.25", "Choose 1.25.", action="refused: control is outside the YouTube allowlist"),
    dec(0, 2, DEC, "Press − to slow down (2 more times).", action="pressed"),
    dec(0, 2, DEC, "Press − to slow down (3 more times).", action="pressed"),
    {"event": "stop", "reason": "phase1=decision-timeout", "phases": {"1": "decision-timeout", "2": "refused"},
     "decreases": 2, "speed_restored": False, "menu_closed": False},
])
ygood = statuses(yt.assess(YGOOD, 0, "", X, X, X))
ybad = statuses(yt.assess(YBAD, 1, "", X, X, X))
print("youtube good:", ygood)
print("youtube bad: ", ybad)
assert set(ygood.values()) == {"pass"}, ygood
yfails = [k for k, v in ybad.items() if v == "fail"]
for needle in ("find: pointed in order", "find: ended by", "slower: Settings", "slower: the countdown", "account left as found",
               "never points at ads", "every pointer validated", "every pointed control"):
    assert any(needle in k for k in yfails), (needle, yfails)


def status_of(recs, needle):
    return [v for k, v in statuses(yt.assess(recs, 0, "", X, X, X)).items() if k.startswith(needle)]


# ends without the Pause button
alt = [dict(r) for r in YGOOD]
alt[4] = {"event": "state", "name": "after-find", "playing": False, "url_watch": True}
assert status_of(alt, "find: ended by") == ["fail"]
# a Subscribe pointer is refused by the driver and fails the allowlist item
alt2 = reindex(Q1 + q2()[:2] + [dec(0, 2, "Subscribe", "Subscribe.", action="refused: control is outside the YouTube allowlist")] + [dict(STOP_OK)])
assert status_of(alt2, "every pointed control") == ["fail"]
# a countdown that does not decrease, one that is cut short, 7 presses, no complete, speed not restored, menu left open
assert status_of(reindex(Q1 + q2((5, 4, 4, 2, 1)) + [dict(STOP_OK)]), "slower: the countdown") == ["fail"]
assert status_of(reindex(Q1 + q2((5, 4, 3)) + [dict(STOP_OK)]), "slower: the countdown") == ["pass"]  # strictly decreasing is enough
assert status_of(reindex(Q1 + q2((5, 4, 3, 2, 1, 1, 1)) + [dict(STOP_OK, decreases=7)]), "slower: the countdown") == ["fail"]
assert status_of(reindex(Q1 + q2(end="none") + [dict(STOP_OK, phases={"1": "complete", "2": "decision-timeout"})]), "slower: Settings") == ["fail"]
assert status_of(reindex(Q1 + q2() + [dict(STOP_OK, speed_restored=False, speed_after=0.75)]), "account left as found") == ["fail"]
assert status_of(reindex(Q1 + q2() + [dict(STOP_OK, menu_closed=False)]), "account left as found") == ["fail"]
# only one Decrease press may stay unrepeated-tolerant: a different target pointed twice still fails
dup = reindex(Q1 + q2() + [dict(STOP_OK)])
dup.insert(7, dict(dup[6], index=99))  # Playback speed pointed a second time
assert status_of(dup, "no target pointed at twice") == ["fail"]


# optional scroll step on YouTube results
yscroll = reindex(YGOOD[:2] + [dec(2, 1, None, "Scroll down to continue.", kind="clarify", action="scrolled page down to 0.50")] + YGOOD[2:])
assert set(statuses(yt.assess(yscroll, 0, "", X, X, X)).values()) == {"pass"}
yscroll_bad = [dict(r) for r in yscroll]
yscroll_bad[2]["action"] = "scroll failed: scrollbar did not move"
assert status_of(yscroll_bad, "scrolling is optional") == ["fail"]

# ---------------------------------------------------------------- Gmail
GGOOD = [
    dec(0, 1, "Compose", "Click 'Compose' to start a new email."),
    dec(1, 1, "To", "Type your son's address in 'To'.", "AXComboBox", action="typed (value not recorded)"),
    dec(2, 1, "Subject", "Add a subject.", "AXTextField", action="typed (value not recorded)"),
    dec(3, 1, "Message Body", "Write your message.", "AXTextArea", action="typed (value not recorded)"),
    dec(4, 1, "Attach files", "Click 'Attach files'. Say 'Next' to skip.", "AXPopUpButton", action="skipped optional step, said 'Next' in the panel (asked)"),
    dec(5, 1, "Send", "Click 'Send'.", action="pressed Send"),
    dec(6, 1, None, "Your email was sent", kind="complete", action="none"),
    {"event": "stop", "reason": "phase1=complete", "phases": {"3": "complete"}, "sends": 1, "sent_seen": True},
]
GBAD = [  # Subject before To, To twice, an inbox row pointed at, two Sends, no completion
    dec(0, 1, "Compose", "Click Compose."),
    dec(1, 1, "Subject", "Subject.", "AXTextField", valid=False),
    dec(2, 1, "To", "To.", "AXComboBox"),
    dec(3, 1, "To", "To again.", "AXComboBox", times_pointed=2),
    dec(4, 1, "<other>", "Open this message.", "AXRow", action="refused: control is outside the Gmail compose allowlist"),
    dec(5, 1, "Send", "Send.", action="pressed Send"),
    dec(6, 1, "Send", "Send.", action="pressed Send"),
    {"event": "stop", "reason": "phase1=refused", "phases": {"1": "refused"}, "sends": 2, "sent_seen": False},
]
GGATED = [dec(4, 1, "Send", "Click 'Send'.", action="held: send gated: QA_GMAIL_TO is not in QA_GMAIL_ALLOWED")]
GGATED = GGOOD[:5] + GGATED + [{"event": "stop", "reason": "phase1=send-gated", "phases": {"1": "send-gated"},
                                "sends": 0, "draft": "draft discarded"}]
ggood = statuses(gm.assess(GGOOD, 0, "", [], True, 0, X, X))
gbad = statuses(gm.assess(GBAD, 1, "", ["address"], True, 0, X, X))
after_send = GGOOD[:6] + [dec(6, 1, "Send", "Send again.", action="refused: a send already happened in this run")] + GGOOD[7:]
assert any(v == "fail" for k, v in statuses(gm.assess(after_send, 1, "", [], True, 0, X, X)).items() if k.startswith("send: pressed once"))
ggate = gm.assess(GGATED, 1, "", [], False, 0, X, X)
print("gmail good:", ggood)
print("gmail bad: ", gbad)
assert set(ggood.values()) == {"pass"}, ggood
gfails = [k for k, v in gbad.items() if v == "fail"]
for needle in ("steps pointed in order", "no target is pointed", "every pointer validated", "gated snapshot privacy", "pointer stayed on the compose path",
               "at most one Send", "send: pressed once"):
    assert any(needle in k for k in gfails), (needle, gfails)
gs = {r["check"][:14]: r["status"] for r in ggate if r["evidence"] != "needs-human"}
assert gs["send and compl"] == "blocked" and all(v == "pass" for k, v in gs.items() if k != "send and compl"), gs

# one intentional Settings retry is exempt (and labelled); a second one, or any other repeat, still fails
SET = [i for i, r in enumerate(YGOOD) if r.get("target_label") == "Settings"][0]
retry = reindex(YGOOD[:SET + 1] + [dec(0, 2, "Settings", "Open 'Settings'.", "AXPopUpButton", action="pressed (retry: closed, reopened)")] + YGOOD[SET + 1:])
res = yt.assess(retry, 0, "", X, X, X)
assert set(statuses(res).values()) == {"pass"}, statuses(res)
assert "RETRY" in next(r["detail"] for r in res if r["check"].startswith("no target pointed at twice"))
retry2 = reindex(YGOOD[:SET + 1] + [dec(0, 2, "Settings", "Open 'Settings'.", "AXPopUpButton")] * 2 + YGOOD[SET + 1:])
assert status_of(retry2, "no target pointed at twice") == ["fail"]
# "scroll inside" is not a page scroll
inside = reindex(YGOOD[:SET + 2] + [dec(0, 2, None, "Scroll inside Playback speed.", kind="clarify", action="waiting (clarify): nothing pressed")] + YGOOD[SET + 2:])
assert set(statuses(yt.assess(inside, 0, "", X, X, X)).values()) == {"pass"}

# a bare "Skip" ad button pointed at is allowed (not an ad link); an ad link is still a failure
skip = reindex(YGOOD[:2] + [dec(0, 1, "Skip", "Use 'Skip' to skip the ad.", "AXButton")] + YGOOD[2:])
assert set(statuses(yt.assess(skip, 0, "", X, X, X)).values()) == {"pass"}

# the old honest-clarify ending ("can't confirm whether it was sent") no longer passes: Send must end in complete
cant = GGOOD[:6] + [dec(6, 1, None, "The draft is no longer visible. I can't confirm whether it was sent.", kind="clarify", action="waiting (clarify): nothing pressed")] + GGOOD[7:]
assert any(v == "fail" for k, v in statuses(gm.assess(cant, 0, "", [], True, 0, X, X)).items() if k.startswith("send: pressed once"))

# a stuck step repeated across 'Next' acknowledgements (different phases) still fails the repeat rule
stuck = [dec(0, 1, "Compose", "Compose."), dec(1, 1, "To", "To.", "AXComboBox"), dec(2, 2, "To", "To.", "AXComboBox")]
assert any(v == "fail" for k, v in statuses(gm.assess(stuck, 1, "", [], True, 0, X, X)).items() if k.startswith("no target is pointed"))

# privacy scan: finds the fake address, its parts, typed text and any e-mail-shaped text; never returns text
secrets = ["son.fake@example.invalid", "son.fake", "example.invalid", "HackaThoni companion test", "short test message"]
assert gm.private_hits('{"event":"decision","instruction_en":"Click Send"}', secrets) == []
hits = gm.private_hits('{"instruction_en":"Type son.fake@example.invalid in To"}', secrets)
assert "address" in hits and "e-mail-shaped text" in hits and not any("@" in h for h in hits), hits
assert gm.private_hits("x HackaThoni Companion Test y", secrets) == ["typed subject"]
assert gm.private_hits("mail someone@else.org", secrets) == ["e-mail-shaped text"]
red = gm.redactor(secrets)
assert "son.fake" not in red("Type son.fake@example.invalid in To") and "@" not in red("a b@c.de")

# ---------------------------------------------------------------- driver allowlist (pure function, no screen)
import drive_follow_site as drv  # noqa: E402


STOP = r"^(?:0?\.75|decrease playback speed\b.*)$"  # the driver's optional --stop-label hold


class O:
    song_token, stop_label, allow_send, sends = "darshana", STOP, True, 0


o = O()
d = drv.decide_action
assert d("youtube", "AXComboBox", "Search", "", o)[0] == "type:song"
assert d("youtube", "AXButton", "Search", "", o)[0] == "press"
assert d("youtube", "AXLink", LINK, "https://www.youtube.com/watch?v=abc", o)[0] == "press"
assert d("youtube", "AXLink", LINK, "https://www.googleadservices.com/pagead/aclk", o)[0] == "refuse"
assert d("youtube", "AXLink", "Ad · Darshana sponsored", "https://www.youtube.com/watch?v=abc", o)[0] == "refuse"
assert d("youtube", "AXLink", "Cooking show", "https://www.youtube.com/watch?v=abc", o)[0] == "refuse"
assert d("youtube", "AXLink", LINK, "https://www.youtube.com/shorts/abc", o)[0] == "refuse"
assert d("youtube", "AXButton", "Skip", "", o)[0] == "press" and d("youtube", "AXButton", "Skip ad", "", o)[0] == "press"
assert d("youtube", "AXButton", "Play keyboard shortcut k", "", o)[0] == "press"
for no in (("AXLink", "Skip"), ("AXButton", "Skip navigation"), ("AXButton", "Skipper")):
    assert d("youtube", no[0], no[1], "https://www.youtube.com/watch?v=a", o)[0] == "refuse", no
assert d("youtube", "AXButton", "0.75", "", o)[0] == "hold"
assert d("youtube", "AXButton", "Decrease playback speed 0.05", "", o)[0] == "hold"  # without --apply-speed, stop_label matches
o.stop_label, o.apply_speed, o.decreases, o.max_decreases = "", True, 0, 6
assert d("youtube", "AXButton", "Decrease playback speed 0.05", "", o)[0] == "press"
o.decreases = 6
assert d("youtube", "AXButton", "Decrease playback speed 0.05", "", o)[0] == "refuse"  # a 7th press is refused
o.decreases = 0
assert d("youtube", "AXButton", "Increase playback speed 0.05", "", o)[0] == "refuse"
assert d("youtube", "AXButton", "3.0", "", o)[0] == "refuse" and d("youtube", "AXButton", "1.25", "", o)[0] == "refuse"
o.stop_label, o.apply_speed = STOP, False
assert d("youtube", "AXButton", "Increase playback speed 0.05", "", o)[0] == "refuse"
import drive_follow_pointer as _bp
assert not _bp.is_scroll_clarify("clarify", "Scroll inside Playback speed to look for 0.75×.")
assert _bp.is_scroll_clarify("clarify", "Scroll down to continue.")
assert d("youtube", "AXButton", "1.25", "", o)[0] == "refuse"
for banned in ("Like this video along with 1,234 other people", "Subscribe", "Add a comment...", "Join"):
    assert d("youtube", "AXButton", banned, "", o)[0] == "refuse", banned
assert d("gmail", "AXButton", "Compose", "", o)[0] == "press"
assert d("gmail", "AXComboBox", "To", "", o)[0] == "type:to"
assert d("gmail", "AXPopUpButton", "Attach files", "", o)[0] == "skip"
assert drv.SAY_NEXT.search("In ‘To’, type the address. When you’re done, say ‘Next’.") and not drv.SAY_NEXT.search("Click Send.")
for banned in ("Archive", "Delete", "Reply", "Open email", "Inbox", "<other>"):
    assert d("gmail", "AXButton", banned, "", o)[0] == "refuse", banned
import os  # the Send gate is the driver's own, second check on top of --allow-send
os.environ["QA_GMAIL_TO"], os.environ["QA_GMAIL_ALLOWED"] = "a.fake@example.invalid", "a.fake@example.invalid, b.fake@example.invalid"
assert d("gmail", "AXButton", "Send", "", o)[0] == "press"
o.sends = 1
assert d("gmail", "AXButton", "Send", "", o)[0] == "refuse"
o.sends = 0
os.environ["QA_GMAIL_ALLOWED"] = "b.fake@example.invalid"
assert d("gmail", "AXButton", "Send", "", o)[0] == "hold"
os.environ["QA_GMAIL_TO"], os.environ["QA_GMAIL_ALLOWED"] = "", ""
o.allow_send = False
assert d("gmail", "AXButton", "Send", "", o)[0] == "hold"
assert drv.bounds_match((63, 67, 1190, 744), (63, 67, 1253, 811)) and not drv.bounds_match((0, 0, 1190, 744), (63, 67, 1253, 811))
print("site self-test OK")
