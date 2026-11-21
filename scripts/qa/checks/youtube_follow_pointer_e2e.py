"""Follow-the-pointer e2e on real YouTube (Safari, Abin's signed-in profile), Sarvam planner, `--task web_site`.

LIVE + SARVAM (about 10-15 chat calls). BLOCKED unless QA_LIVE_SARVAM=1, a SARVAM_API_KEY exists, the YouTube
pack with its start_guidance hook is on this branch, and the process is Accessibility-trusted.

Walk 1, Malayalam question "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ" (play the Darshana song): Search box (the driver types
"Darshana Hridayam") -> Search button -> the matching /watch result link -> playback started (pack says complete).
The driver then pauses the video (quiet Mac) and asks walk 2 in the panel, "make it slower": Settings -> Playback
speed -> "Decrease playback speed 0.05", pressed each time it is pointed (max 6), the instruction counting down
"(N more times)" until the slider reads 0.75 and the pack says complete. Afterwards the driver restores Normal speed
(the 1.0 preset) and closes Settings, so the account is left as found. No like, subscribe or comment is touched.
Everything happens in one Safari window this check opens and closes itself.
Driver: scripts/drive_follow_site.py (allowlist, ad guard, never presses an unmatched control).
"""
import os
import re

from _common import result
import _follow
import _site

FEATURE = "web-support"
QUESTION = os.environ.get("QA_YT_QUESTION", "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ")
THEN_ASK = os.environ.get("QA_YT_SLOWER", "make it slower")
SONG_TEXT, SONG_TOKEN = "Darshana Hridayam", "darshana"
URL, HOST, PREFIX = "https://www.youtube.com/", "youtube.com", "https://www.youtube.com/"
# YouTube's speed panel has presets 1.0, 1.25, 1.5, 2.0, 3.0 and a 0.05 stepper but no 0.75 button: the pointer lands on
# "Decrease playback speed 0.05" (five presses from Normal reach 0.75).
DECREASE = re.compile(r"^decrease playback speed\b", re.IGNORECASE)
MAX_DECREASES = 6
COUNTDOWN = re.compile(r"\((\d+) more times?\)")
AD = re.compile(r"\b(ad|ads|advert|advertisement|sponsored)\b", re.IGNORECASE)
SEARCH_ROLES = {"AXComboBox", "AXSearchField", "AXTextField"}
SKIP_AD = re.compile(r"^(?:skip ads?\b|skip$)", re.IGNORECASE)  # the ad buttons the pack may offer
TYPE_FROM_INSTRUCTION = os.environ.get("QA_YT_TYPE_FROM_INSTRUCTION") == "1"


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
    ("Decrease playback speed stepper", lambda r: DECREASE.match(_lab(r)) is not None),
]


def find_route(pts1):
    """(ok, detail). Two valid routes: Search box -> Search button -> matching result, or, when the start page (a signed-in home
    feed) already lists the song, pointing straight at that result (the shortcut)."""
    ok, d = _site.order_check(pts1, FIND_STEPS)
    if ok:
        return True, f"route: search; {d}"
    if pts1 and FIND_STEPS[2][1](pts1[0]) and not any(FIND_STEPS[0][1](r) or FIND_STEPS[1][1](r) for r in pts1):
        return True, f"route: feed shortcut (the start page already listed the song); {d}"
    return False, d


def title_led(pts1):
    """The chosen result is the song itself: its title starts with the name, not a credit-list match ('Nagumo ... | Darshana')."""
    links = [r for r in pts1 if r.get("target_role") == "AXLink"]
    labels = [(r.get("target_label") or "").strip() for r in links]
    return bool(labels) and all(l.lower().startswith(SONG_TOKEN) for l in labels), labels


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
                                           "--apply-speed", "--max-decreases", str(MAX_DECREASES), "--then-ask", THEN_ASK,
                                           *(["--type-from-instruction"] if TYPE_FROM_INSTRUCTION else [])],
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

    ok, d = find_route(pts1)
    add("find: pointed in order Search box, Search button, matching result (or straight at it when the start page lists it)", ok, f"{d}; {where}")
    led, labels = title_led(pts1)
    add("find: the chosen video is the song itself (title starts with the name), not a credit-list match", led,
        f"chosen {[l[:60] for l in labels]}")

    last1 = [r for r in decisions if r.get("phase") == 1][-1:] or [None]
    playing = state.get("playing") is True and state.get("url_watch") is True
    done1 = phases.get("1", phases.get(1)) == "complete" and last1[0] is not None and last1[0]["kind"] == "complete"
    add("find: ended by a complete decision with the video actually playing (Pause shown on a /watch page)",
        done1 and playing,
        f"phase 1 end={phases.get('1', phases.get(1))}; driver read playing={state.get('playing')}, watch URL={state.get('url_watch')}; "
        f"search fallback={stop.get('search_fallback')}")

    ok, d = _site.order_check(pts2, SPEED_STEPS)
    p2end = phases.get("2", phases.get(2))
    diag = next((r for r in records if r["event"] == "diagnostic"), None)
    last2 = [r for r in decisions if r.get("phase") == 2][-1:] or [None]
    done2 = p2end == "complete" and last2[0] is not None and last2[0]["kind"] == "complete" and "0.75" in last2[0].get("instruction_en", "")
    add("slower: Settings, Playback speed, Decrease pressed each time pointed, ended by complete at 0.75", ok and done2,
        f"{d}; phase 2 end={p2end}; last decision {last2[0]['kind'] if last2[0] else None}: "
        f"{(last2[0] or {}).get('instruction_en', '')[:60]!r}; {where}",
        f"\nREADER ROWS at the stall (role, label, enabled, filled): {diag}" if diag else "")

    dec_pts = [r for r in pts2 if DECREASE.match(_lab(r))]
    counts = [int(m.group(1)) for r in dec_pts if (m := COUNTDOWN.search(r.get("instruction_en", "")))]
    pressed = [r for r in dec_pts if str(r.get("action", "")).startswith("pressed")]
    strictly = all(a > b for a, b in zip(counts, counts[1:])) and len(counts) >= 1
    exact = counts == [5, 4, 3, 2, 1] or counts == [5, 4, 3, 2]  # the last step may read "(1 more time)" or complete first
    add("slower: the countdown strictly decreases (5, 4, 3, 2, 1) and at most 6 presses", strictly and 1 <= len(pressed) <= MAX_DECREASES,
        f"Decrease pointed {len(dec_pts)} times, pressed {len(pressed)}; countdown read {counts} "
        f"({'exactly 5,4,3,2,1' if counts == [5, 4, 3, 2, 1] else 'strictly decreasing, not the full 5..1' if strictly else 'NOT decreasing'}); "
        f"driver re-presses because the slider had not moved: {stop.get('decrease_retries', 0)}")

    restored = stop.get("speed_restored") is True and stop.get("menu_closed") is True
    add("account left as found: speed back to Normal (1.0) and Settings closed", restored,
        f"speed restored={stop.get('speed_restored')} (last slider reading {stop.get('speed_after')}), settings closed={stop.get('menu_closed')}, "
        f"Decrease presses={stop.get('decreases')}")

    rep = _site.repeats(allpts, allow={"settings": 1, "decrease playback speed 0.05": MAX_DECREASES})
    retries = [r["index"] for r in allpts if (r.get("target_label") or "").strip().lower() == "settings"][1:]
    add("no target pointed at twice (per question; one Settings retry and the Decrease stepper presses are expected)", not rep,
        f"repeated targets: {rep}; stop {stop['reason']}" if rep else
        "every target pointed at once (the Decrease stepper is pointed once per press, up to 6)" + (f"; Settings pointed again in decisions {retries} (RETRY, exempt: allowed exactly once)" if retries else ""))

    bad = []
    for r in allpts:
        lab = r.get("target_label") or ""
        if r.get("target_role") == "AXLink":
            if r.get("phase") == 2 or SONG_TOKEN not in lab.lower() or r.get("url_watch") is False or AD.search(lab):
                bad.append((r["index"], r.get("target_role"), lab[:60]))
        elif AD.search(lab) and not SKIP_AD.match(lab):
            bad.append((r["index"], r.get("target_role"), lab[:60]))
    skip_ad = [r["index"] for r in allpts if SKIP_AD.match((r.get("target_label") or "").strip())]
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
