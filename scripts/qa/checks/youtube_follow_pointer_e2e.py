"""Follow-the-pointer e2e on real YouTube (Safari, Abin's signed-in profile), Sarvam planner, `--task web_site`.

LIVE + SARVAM (about 10-15 chat calls). BLOCKED unless QA_LIVE_SARVAM=1, a SARVAM_API_KEY exists, the YouTube
pack with its start_guidance hook is on this branch, and the process is Accessibility-trusted.

Walk 1, Malayalam question "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ" (play the Darshana song): Search box (the driver types
"Darshana Hridayam") -> Search button -> the matching /watch result link -> playback started (pack says complete).
The driver then pauses the video (quiet Mac) and asks walk 2 in the panel, "Play it slower": Settings -> Playback
speed -> the pointer lands on 0.75. The driver STOPS there and presses nothing: no setting is applied, no like,
subscribe or comment is touched. Everything happens in one Safari window this check opens and closes itself.
Driver: scripts/drive_follow_site.py (allowlist, ad guard, never presses an unmatched control).
"""
import os
import re

from _common import result
import _follow
import _site

FEATURE = "web-support"
QUESTION = os.environ.get("QA_YT_QUESTION", "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ")
THEN_ASK = os.environ.get("QA_YT_SLOWER", "Play it slower")  # known pack phrase; "make it slower" does not parse
SONG_TEXT, SONG_TOKEN = "Darshana Hridayam", "darshana"
URL, HOST, PREFIX = "https://www.youtube.com/", "youtube.com", "https://www.youtube.com/"
STOP_LABEL = r"^0?\.75$"
AD = re.compile(r"\b(ad|ads|advert|advertisement|sponsored)\b", re.IGNORECASE)
SEARCH_ROLES = {"AXComboBox", "AXSearchField", "AXTextField"}


def _lab(r):
    return (r.get("target_label") or "").strip().lower()


FIND_STEPS = [
    ("Search box", lambda r: r.get("target_role") in SEARCH_ROLES and _lab(r) == "search"),
    ("Search button", lambda r: r.get("target_role") == "AXButton" and _lab(r) == "search"),
    ("matching result link", lambda r: r.get("target_role") == "AXLink" and SONG_TOKEN in _lab(r)),
]
SPEED_STEPS = [
    ("Settings", lambda r: _lab(r) == "settings"),
    ("Playback speed", lambda r: _lab(r).startswith("playback speed")),
    ("0.75", lambda r: re.fullmatch(STOP_LABEL, _lab(r)) is not None),
]


def run():
    name = "youtube follow-the-pointer (Sarvam planner, Malayalam question, search -> play -> slower)"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: live Sarvam planner (~10-15 chat calls); opens one Safari window on YouTube "
                       "(signed in as Abin; search + play + open the speed menu only) and plays about 10 s of one video")]
    why = _site.pack_landed("YouTube", "youtube")
    if why:
        return [result(FEATURE, name, "blocked", "blocked", why)]
    if not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]

    err, ctx = _site.run_walk(site="youtube", url=URL, host=HOST, ready_prefix=PREFIX, question=QUESTION,
                              driver_args=["--song-text", SONG_TEXT, "--song-token", SONG_TOKEN,
                                           "--stop-label", STOP_LABEL, "--then-ask", THEN_ASK],
                              total_timeout=240)
    if err:
        return err
    return assess(ctx["records"], ctx["rc"], ctx["stderr"], ctx["started"], ctx["out_file"], ctx["log"])


def assess(records, driver_rc, driver_err, started, out_file, log):
    decisions = [r for r in records if r["event"] == "decision"]
    stop = _site.stop_of(records, driver_rc, driver_err)
    phases = stop.get("phases") or {}
    pts1, pts2 = _site.points(records, 1), _site.points(records, 2)
    allpts = pts1 + pts2
    full = _site.decision_list(records)
    print(f"\n--- youtube follow-the-pointer: {len(decisions)} decisions, stop={stop['reason']} ---\n{full}\n--- end ---")
    where = f"decision list: {out_file}; session log: {log}"
    state = next((r for r in records if r["event"] == "state"), {})
    out = []

    def add(check, ok, detail, fail_extra=""):
        out.append(result(FEATURE, check, "pass" if ok else "fail", "live-machine",
                          detail if ok else f"{detail}{fail_extra}\nDECISIONS:\n{full}"))

    ok, d = _site.order_check(pts1, FIND_STEPS)
    add("find: pointed in order Search box, Search button, matching result", ok, f"{d}; {where}")

    last1 = [r for r in decisions if r.get("phase") == 1][-1:] or [None]
    playing = state.get("playing") is True and state.get("url_watch") is True
    done1 = phases.get("1", phases.get(1)) == "complete" and last1[0] is not None and last1[0]["kind"] == "complete"
    add("find: ended by a complete decision with the video actually playing (Pause shown on a /watch page)",
        done1 and playing,
        f"phase 1 end={phases.get('1', phases.get(1))}; driver read playing={state.get('playing')}, watch URL={state.get('url_watch')}; "
        f"search fallback={stop.get('search_fallback')}")

    ok, d = _site.order_check(pts2, SPEED_STEPS)
    reached = phases.get("2", phases.get(2)) == "reached-target"
    add("slower: pointed in order Settings, Playback speed, 0.75 (target asserted)", ok and reached,
        f"{d}; phase 2 end={phases.get('2', phases.get(2))}; {where}")

    pressed_target = [r["index"] for r in pts2 if SPEED_STEPS[2][1](r) and str(r.get("action", "")).startswith("pressed")]
    add("no setting applied: the driver stopped at 0.75 and pressed nothing there",
        not pressed_target and reached, f"pressed 0.75 in decisions {pressed_target}; phase 2 end={phases.get('2', phases.get(2))}")

    rep = _site.repeats(allpts)
    add("no target pointed at twice (per question)", not rep, f"repeated targets: {rep}; stop {stop['reason']}")

    bad = []
    for r in allpts:
        lab = r.get("target_label") or ""
        if r.get("target_role") == "AXLink":
            if r.get("phase") == 2 or SONG_TOKEN not in lab.lower() or r.get("url_watch") is False or AD.search(lab):
                bad.append((r["index"], r.get("target_role"), lab[:60]))
        elif AD.search(lab) and not re.match(r"skip ads?\b", lab, re.IGNORECASE):
            bad.append((r["index"], r.get("target_role"), lab[:60]))
    skip_ad = [r["index"] for r in allpts if re.match(r"skip ads?\b", (r.get("target_label") or ""), re.IGNORECASE)]
    add("never points at ads or unrelated links (every link names the song and is a /watch result)", not bad,
        f"ad or unrelated targets: {bad}" if bad else f"links pointed at: {[r.get('target_label')[:50] for r in allpts if r.get('target_role') == 'AXLink']}; "
        f"'Skip ad' pointed at in decisions {skip_ad} (allowed: the pack offers it while an ad plays)")

    invalid = [r["index"] for r in allpts if r.get("valid") is not True]
    add("every pointer validated", not invalid and bool(decisions),
        f"unvalidated decisions {invalid}" if invalid else f"{len(decisions)} decisions, sources {sorted({r.get('source') for r in decisions})}")

    refused = [(r["index"], r.get("action")) for r in decisions if str(r.get("action", "")).startswith(("refused", "no matching"))]
    add("every pointed control was inside the driver's allowlist and matched on the page", not refused,
        f"driver refused or could not match: {refused}" if refused else "no refusals, every frame matched a control of our window")

    out.append(_follow.scroll_result(FEATURE, decisions))
    out.append(result(FEATURE, "person follows the pointer on real YouTube; Malayalam reads naturally; ads handled", "skip",
                      "needs-human", "driver pressed Search/result/Settings/Playback speed through Accessibility; a person has not run this"))
    return out
