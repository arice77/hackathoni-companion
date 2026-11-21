"""YouTube player controls on real YouTube (Safari, Abin's signed-in profile), Sarvam planner, `--task web_site`.

LIVE + SARVAM (about 6 questions, 40-60 chat calls incl. intent calls). BLOCKED unless QA_LIVE_SARVAM=1, a SARVAM_API_KEY exists
and the process is Accessibility-trusted. Run only when nobody is using the Mac (it plays a video; sound is muted early).

One Safari window of its own: Q1 finds and plays the Darshana song (as youtube_follow_pointer_e2e), then, with the video playing:
  mute        -> Mute pressed, complete "muted"
  pause       -> Pause pressed, complete "paused"
  resume      -> Play pressed, complete "playing"
  speed it up -> Settings, Playback speed, the 1.25 preset pressed, complete "1.25" (then speed back to Normal, menus closed)
  full screen -> the Full screen button is POINTED AT with "Esc" in the instruction; the driver does NOT press it (AXPress would
                 move Safari into its own full-screen Space); the Esc half stays a human check
  malayalam subtitles -> honest: either Malayalam gets selected, or the pack says it is not available ("unsupported")
Tidy-up at the end, read back from the page: captions off, speed Normal, Settings closed, unmuted, video paused. Never a like,
subscribe or comment. Driver: scripts/drive_follow_site.py --player-controls.
"""
import os
import re

from _common import result
import _follow
import _site
import youtube_follow_pointer_e2e as base_check

FEATURE = "web-support"
QUESTION = os.environ.get("QA_YT_QUESTION", "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ")
ASKS = [("mute", ""), ("pause", ""), ("resume", ""), ("speed it up", "speed"), ("full screen", ""), ("malayalam subtitles", "menu")]
SHORTCUT = re.compile(r"(?:\s*\([a-z]\)|\s+keyboard shortcut\s+[a-z])$")


def _pl(r):
    return SHORTCUT.sub("", (r.get("target_label") or "").strip().lower())


def _pressed(r):
    return str(r.get("action", "")).startswith("pressed")


SPECS = {
    2: ("mute", [("Mute", lambda r: _pl(r) == "mute")], "complete", "muted"),
    3: ("pause", [("Pause", lambda r: _pl(r) == "pause")], "complete", "paused"),
    4: ("resume", [("Play", lambda r: _pl(r) == "play")], "complete", "playing"),
    5: ("speed it up", [("Settings", lambda r: _pl(r) == "settings"), ("Playback speed", lambda r: _pl(r).startswith("playback speed")),
                        ("1.25 preset", lambda r: _pl(r) == "1.25")], "complete", "1.25"),
    6: ("full screen", [("Full screen", lambda r: _pl(r) == "full screen")], "reached-target", None),
    7: ("malayalam subtitles", [], None, None),  # honest either way: checked separately
}


def run():
    name = "youtube player controls (mute, pause, resume, faster, full screen pointer, subtitles) + tidy-up"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: live Sarvam planner, plays a video on Abin's YouTube (muted early, paused at the end); "
                       "run when the Mac is free")]
    why = _site.pack_landed("YouTube", "youtube")
    if why:
        return [result(FEATURE, name, "blocked", "blocked", why)]
    if not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    args = ["--song-text", base_check.SONG_TEXT, "--song-token", base_check.SONG_TOKEN, "--player-controls", "--allow-presets", "1.25",
            "--keep-playing"]
    for text, kind in ASKS:
        args += ["--then-ask", f"{text}::{kind}" if kind else text]
    err, ctx = _site.run_walk(site="youtube", url=base_check.URL, host=base_check.HOST, ready_prefix=base_check.PREFIX,
                              question=QUESTION, driver_args=args, total_timeout=420, decision_timeout=50)
    if err:
        return err
    return assess(ctx["records"], ctx["rc"], ctx["stderr"], ctx["started"], ctx["out_file"], ctx["log"])


def assess(records, driver_rc, driver_err, started, out_file, log):
    decisions = [r for r in records if r["event"] == "decision"]
    stop = _site.stop_of(records, driver_rc, driver_err)
    phases = {int(k): v for k, v in (stop.get("phases") or {}).items()}
    full = _site.decision_list(records)
    print(f"\n--- youtube player controls: {len(decisions)} decisions, stop={stop['reason']} ---\n{full}\n--- end ---")
    where = f"decision list: {out_file}; session log: {log}"
    out = []

    def add(check, ok, detail):
        out.append(result(FEATURE, check, "pass" if ok else "fail", "live-machine", detail if ok else f"{detail}\nDECISIONS:\n{full}"))

    pts1 = _site.points(records, 1)
    ok, d = _site.order_check(pts1, base_check.FIND_STEPS)
    state = next((r for r in records if r["event"] == "state"), {})
    last1 = [r for r in decisions if r.get("phase") == 1][-1:] or [None]
    add("find: Search box, Search button, matching result, complete with the video playing",
        ok and phases.get(1) == "complete" and last1[0] is not None and last1[0]["kind"] == "complete" and state.get("playing") is True,
        f"{d}; phase 1 end={phases.get(1)}; playing={state.get('playing')}; {where}")

    for phase, (label, steps, end, text) in SPECS.items():
        pts = _site.points(records, phase)
        ds = [r for r in decisions if r.get("phase") == phase]
        last = ds[-1] if ds else None
        if phase == 7:
            allowed = {"subtitles/closed captions", "settings", "subtitles/cc", "malayalam"}
            odd = [_pl(r) for r in pts if not any(_pl(r).startswith(a) for a in allowed)]
            honest = phases.get(phase) in {"complete", "unsupported"} and last is not None and last["kind"] in {"complete", "unsupported"}
            add(f"[{label}] ends honestly: Malayalam selected, or 'not available' (unsupported); nothing else pointed at",
                honest and not odd, f"phase end={phases.get(phase)}; last {last['kind'] if last else None}: "
                f"{(last or {}).get('instruction_en', '')[:70]!r}; unexpected targets {odd}")
            continue
        ok, d = _site.order_check(pts, steps)
        kind_ok = phases.get(phase) == end and last is not None and (last["kind"] == "complete" if end == "complete" else True)
        text_ok = text is None or (last is not None and text in last.get("instruction_en", "").lower())
        acted = all(_pressed(r) for r in pts if steps and steps[-1][1](r)) if end == "complete" else True
        extra = ""
        if phase == 6:
            fs = [r for r in pts if _pl(r) == "full screen"]
            esc = bool(fs) and "esc" in fs[0].get("instruction_en", "").lower()
            held = bool(fs) and str(fs[0].get("action", "")).startswith("held")
            ok, kind_ok, text_ok, acted = ok and esc and held, True, True, True
            extra = f"; 'Esc' in the instruction={esc}; held, not pressed={held}"
        add(f"[{label}] pointed in order {', '.join(s[0] for s in steps)} and ended {end}" + (f" ('{text}')" if text else ""),
            ok and kind_ok and text_ok and acted, f"{d}; phase end={phases.get(phase)}{extra}")

    rep = _site.repeats(_site.points(records), allow={"settings": 1})
    add("no target pointed at twice within a question (one Settings retry allowed)", not rep, f"repeated: {rep}")
    invalid = [r["index"] for r in decisions if r["kind"] == "point" and r.get("valid") is not True]
    add("every pointer validated", not invalid and bool(decisions), f"unvalidated decisions {invalid}")
    refused = [(r["index"], r.get("action")) for r in decisions if str(r.get("action", "")).startswith(("refused", "no matching"))]
    add("every pointed control was inside the driver's allowlist and matched on the page", not refused, f"refused/unmatched: {refused}")
    tidy = stop.get("tidy") or {}
    need = ("captions_off", "speed_restored", "menu_closed", "unmuted", "paused")
    add("account left as found: captions off, speed Normal, Settings closed, unmuted, video paused",
        all(tidy.get(k) is True for k in need), f"tidy read-back {tidy}")
    out.append(result(FEATURE, "person follows the pointer on YouTube controls, presses Esc in full screen, hears the Malayalam", "skip",
                      "needs-human", "Full screen is pointed at but never pressed by the driver; Esc and the spoken Malayalam stay human checks"))
    return out
