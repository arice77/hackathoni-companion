"""Abin's real Gmail phrasings through the full compose walk, with a human-like driver (live, Sarvam planner, own Safari window each).

Hand test 22 Nov found two bugs the one-phrase check missed: natural sentences ("I need to send an email to my son.",
"എനിക്കൊരു ഇമെയിൽ അയക്കണം.", "I want to write a mail") got "I can help write…" with no steps, and after typing the address and clicking
Subject Gmail collapses To into a recipients summary, so the guide bounced between To and Subject.

Each phrasing is one walk: Compose -> To -> Subject -> Message Body -> Send (no Attach step since Abin's 22 Nov 04:15 decision). Only the LAST phrasing
presses Send (one message to the allowlisted address, "Message sent", then complete "Your email was sent"); every earlier walk stops AT
the Send pointer (held, not pressed) and discards its own draft. At most one send per run.
Driver option A (default, human-like): type the address, do NOT press Return, move straight on to Subject. Option B: QA_GMAIL_TO_RETURN=1
presses Return after the address. Phrasings: edit PHRASES or set QA_GMAIL_PHRASES='["..."]' (the last one sends).
Never prints or logs the address, subjects or bodies (same scan as gmail_follow_pointer_e2e).
"""
import json
import os

from _common import result
import _follow
import _site
import gmail_follow_pointer_e2e as gm

FEATURE = "web-support"
PHRASES = ["I need to send an email to my son.", "എനിക്കൊരു ഇമെയിൽ അയക്കണം.", "I want to write a mail", "Ente makanu oru email ayakkanam"]
SEND_NAME = "send and completion"


def phrases():
    raw = os.environ.get("QA_GMAIL_PHRASES")
    return json.loads(raw) if raw else PHRASES


def run():
    name = "gmail phrasings (natural sentences, human-like driver, one send in the whole run)"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: one Safari window per phrasing on Abin's Gmail; compose only, the last phrasing sends "
                       "one message to the allowlisted address")]
    why = _site.pack_landed("Gmail", "gmail")
    if why:
        return [result(FEATURE, name, "blocked", "blocked", why)]
    if not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    to_set, allowed = gm.send_gate()
    if not to_set:
        return [result(FEATURE, name, "blocked", "blocked", "QA_GMAIL_TO is not set (env or repo-root .env)")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    to = gm._env("QA_GMAIL_TO")
    local, _, domain = to.partition("@")
    secrets = [to, local, domain, gm.SUBJECT_TEXT, gm.BODY_TEXT]
    out, sends = [], 0
    items = phrases()
    for i, phrase in enumerate(items, 1):
        last = i == len(items)
        args = (["--allow-send"] if last and allowed else []) + (["--to-return"] if os.environ.get("QA_GMAIL_TO_RETURN") == "1" else [])
        err, ctx = _site.run_walk(site="gmail", url=gm.URL, host=gm.HOST, ready_prefix=gm.PREFIX, question=phrase,
                                  driver_args=args, total_timeout=180)
        if err:
            return out + err
        log_text = ctx["log"].read_text() if ctx["log"].exists() else ""
        stop = _site.stop_of(ctx["records"], ctx["rc"], ctx["stderr"])
        sends += int(stop.get("sends") or 0)
        out += assess_phrase(i, phrase, last, ctx["records"], ctx["rc"], ctx["stderr"], gm.private_hits(log_text, secrets), allowed,
                             ctx["started"], ctx["out_file"], ctx["log"], gm.redactor(secrets))
    out.append(result(FEATURE, "exactly one message was sent in the whole run" if allowed else "no message was sent (send not allowed)",
                      "pass" if sends == (1 if allowed else 0) else "fail", "live-machine", f"sends across {len(items)} walks: {sends}"))
    return out


def assess_phrase(i, phrase, sending, records, rc, err, hits, allowed, started, out_file, log, redact=None):
    """The base Gmail assessment for one phrasing, plus: a non-sending walk must stop AT the Send pointer (held) and discard its draft."""
    res = gm.assess(records, rc, err, hits, sending and allowed, started, out_file, log, redact)
    stop = _site.stop_of(records, rc, err)
    decisions = [r for r in records if r["event"] == "decision"]
    tag = f"[phrase {i}: {phrase[:28]!r}{' · sends' if sending else ' · stops at Send'}] "
    fixed = []
    for r in res:
        r = dict(r)
        if r["check"] == SEND_NAME and not sending:
            last_point = next((d for d in reversed(decisions) if d["kind"] == "point"), None)
            held = bool(last_point and last_point.get("target_label") == "Send" and str(last_point.get("action", "")).startswith("held"))
            drafted = stop.get("draft") == "draft discarded"
            r.update(check="stops at the Send pointer without pressing it, draft discarded", status="pass" if held and drafted else "fail",
                     evidence="live-machine", detail=f"Send pointed at and held={held}, draft: {stop.get('draft')}, driver stop={stop['reason']}")
        r["check"] = tag + r["check"]
        fixed.append(r)
    return fixed
