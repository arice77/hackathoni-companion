"""Follow-the-pointer e2e on real Gmail (Safari, Abin's signed-in account), Sarvam planner, `--task web_site`.

LIVE + SARVAM. BLOCKED unless QA_LIVE_SARVAM=1, a SARVAM_API_KEY exists, the Gmail pack with its start_guidance hook
is on this branch, QA_GMAIL_TO is set (env or repo-root .env) and the process is Accessibility-trusted.

Question (Malayalam) "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം" (I want to send an email to my son). Walk: Compose -> To (the
driver types QA_GMAIL_TO) -> Subject -> Message Body (a short neutral line) -> Send. The pack also offers an optional
"Attach files" step (the driver skips it without opening the dialog) and asks the person to say "Next" after a field
whose state it cannot read; the driver says "Next" in the companion panel when the instruction asks for it. The pack
never claims a send happened ("I can't confirm whether it was sent"), so the end is read from Gmail's own "Message
sent" notice, not from a complete decision.

Send gate: the driver presses Send ONLY if QA_GMAIL_TO is in the comma-separated QA_GMAIL_ALLOWED, at most once per
run. Otherwise it stops before Send, discards its own draft, and the completion item reports BLOCKED. It never
opens, archives, deletes or marks other mail. Nothing private is printed or logged: this file, the driver and the
decision list refer only to "Abin's address"; the session log is scanned (not printed) for the address, the typed
subject and body, and any e-mail-shaped text.
"""
import os
import re

from _common import ROOT, result
import _follow
import _site

FEATURE = "web-support"
QUESTION = "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം"
URL, HOST, PREFIX = "https://mail.google.com/mail/u/0/#inbox", "mail.google.com", "https://mail.google.com/"
SUBJECT_TEXT = "HackaThoni companion test"
BODY_TEXT = "This is a short test message from the HackaThoni companion check. Please ignore it."
STEPS = [
    ("Compose", lambda r: r.get("target_role") == "AXButton" and r.get("target_label") == "Compose"),
    ("To", lambda r: r.get("target_label") == "To"),
    ("Subject", lambda r: r.get("target_label") == "Subject"),
    ("Message Body", lambda r: r.get("target_label") == "Message Body"),
    ("Send", lambda r: r.get("target_role") == "AXButton" and r.get("target_label") == "Send"),
]


def _env(name):
    sys_path = str(ROOT / "scripts")
    import sys
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import importlib
    return importlib.import_module("drive_follow_site").env_value(name)


def send_gate():
    """(to_set, send_allowed) from QA_GMAIL_TO / QA_GMAIL_ALLOWED. Values are never returned."""
    to = _env("QA_GMAIL_TO").strip().lower()
    allowed = {a.strip().lower() for a in _env("QA_GMAIL_ALLOWED").split(",") if a.strip()}
    return bool(to), bool(to) and to in allowed


def private_hits(log_text: str, secrets: list[str]) -> list[str]:
    """Categories of private text found in the session log. Never returns the text itself."""
    hits = []
    low = log_text.lower()
    names = ("address", "address local part", "address domain")
    for n, s in zip(names, secrets[:3]):
        if s and s.lower() in low:
            hits.append(n)
    if secrets[3] and secrets[3].lower() in low:
        hits.append("typed subject")
    if secrets[4] and secrets[4].lower() in low:
        hits.append("typed body")
    if _site.EMAIL.search(log_text):
        hits.append("e-mail-shaped text")
    return hits


def redactor(secrets):
    def red(text):
        for s in secrets:
            if s:
                text = re.sub(re.escape(s), "[redacted]", text, flags=re.IGNORECASE)
        return _site.EMAIL.sub("[redacted]", text)
    return red


def run():
    name = "gmail follow-the-pointer (Sarvam planner, Malayalam question, compose -> send)"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: live Sarvam planner; opens one Safari window on Abin's Gmail, composes one "
                       "message and sends it only if QA_GMAIL_TO is in QA_GMAIL_ALLOWED")]
    why = _site.pack_landed("Gmail", "gmail")
    if why:
        return [result(FEATURE, name, "blocked", "blocked", why)]
    if not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    to_set, allowed = send_gate()
    if not to_set:
        return [result(FEATURE, name, "blocked", "blocked", "QA_GMAIL_TO is not set (env or repo-root .env)")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]

    err, ctx = _site.run_walk(site="gmail", url=URL, host=HOST, ready_prefix=PREFIX, question=QUESTION,
                              driver_args=["--allow-send"] if allowed else [], total_timeout=240)
    if err:
        return err
    to = _env("QA_GMAIL_TO")
    local, _, domain = to.partition("@")
    secrets = [to, local, domain, SUBJECT_TEXT, BODY_TEXT]
    log_text = ctx["log"].read_text() if ctx["log"].exists() else ""
    return assess(ctx["records"], ctx["rc"], ctx["stderr"], private_hits(log_text, secrets), allowed,
                  ctx["started"], ctx["out_file"], ctx["log"], redactor(secrets))


def assess(records, driver_rc, driver_err, privacy_hits, send_allowed, started, out_file, log, redact=None):
    decisions = [r for r in records if r["event"] == "decision"]
    stop = _site.stop_of(records, driver_rc, driver_err)
    phases = stop.get("phases") or {}
    pts = _site.points(records)
    full = _site.decision_list(records, redact)
    print(f"\n--- gmail follow-the-pointer: {len(decisions)} decisions, stop={stop['reason']} ---\n{full}\n--- end ---")
    where = f"decision list: {out_file}; session log: {log}"
    out = []

    def add(check, ok, detail):
        out.append(result(FEATURE, check, "pass" if ok else "fail", "live-machine",
                          detail if ok else f"{detail}\nDECISIONS:\n{full}"))

    ok, d = _site.order_check(pts, STEPS)
    add("steps pointed in order: Compose, To, Subject, Message Body, Send", ok, f"{d}; {where}")

    rep = _site.repeats(pts, by_phase=False)  # saying 'Next' starts a new question; a stuck step must still count
    add("no target is pointed at twice", not rep, f"repeated targets: {rep}; stop {stop['reason']}")

    invalid = [r["index"] for r in pts if r.get("valid") is not True]
    add("every pointer validated", not invalid and bool(decisions),
        f"unvalidated decisions {invalid}" if invalid else f"{len(decisions)} decisions, sources {sorted({r.get('source') for r in decisions})}")

    other = [r["index"] for r in pts if r.get("target_label") not in {s[0] for s in STEPS} | {"Attach files"}]
    add("gated snapshot privacy: no private text in the session log, only fixed names pointed at",
        not privacy_hits and not other,
        f"private text categories found in the session log: {privacy_hits}; pointed at non-compose controls in decisions {other}"
        if privacy_hits or other else "no address, typed text or e-mail-shaped text in any session log line; every target is a fixed Gmail name")

    refused = [(r["index"], r.get("action")) for r in decisions if str(r.get("action", "")).startswith(("refused", "no matching"))]
    add("pointer stayed on the compose path (never at other mail, archive, delete, labels)", not refused,
        f"driver refused or could not match: {refused}" if refused else "no refusals")

    sends = [r for r in decisions if r.get("action") == "pressed Send"]
    add("at most one Send per run", len(sends) <= 1, f"Send pressed {len(sends)} time(s)")

    last = decisions[-1] if decisions else None
    if not send_allowed:
        out.append(result(FEATURE, "send and completion", "blocked", "blocked",
                          f"stopped before Send: QA_GMAIL_TO is not in QA_GMAIL_ALLOWED. Walk to Send asserted above; "
                          f"driver stop={stop['reason']}; draft: {stop.get('draft')}"))
    else:
        sent = len(sends) == 1 and stop.get("sent_seen") is True
        send_idx = sends[0]["index"] if sends else None
        later = [r for r in decisions if send_idx is not None and r["index"] > send_idx]
        again = [r["index"] for r in later if r["kind"] == "point"]
        done = bool(last and last["kind"] == "complete" and "sent" in last.get("instruction_en", "").lower())
        add("send: pressed once to Abin's own address, 'Message sent' seen, ended by complete 'Your email was sent', nothing pointed at after it",
            sent and not again and done,
            f"sends={len(sends)}, message-sent notice seen={stop.get('sent_seen')}, decisions after Send {[(r['kind']) for r in later]}, "
            f"pointed again after Send: {again}; last decision {last['kind'] if last else None}; driver stop={stop['reason']}; {where}")
    out.append(result(FEATURE, "person follows the pointer in Gmail; Malayalam reads naturally", "skip", "needs-human",
                      "driver typed the recipient, subject and body through Accessibility; a person has not run this"))
    return out
