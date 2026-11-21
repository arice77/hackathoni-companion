"""YouTube regression replays (offline): Abin's hand-test bugs 3-7 and the player-control walks, no Safari, no Sarvam.

Synthetic Accessibility states go through the real SarvamPlanner (`--task web_site` wiring: pack lookup, local intent
parse, the one Sarvam intent call, YouTube guide, validator) with the network blocked. Where a sentence needs the one
intent call, a MOCK provider answers it, and the scenario counts that exactly one call was made. Live coverage of the same
behaviour is youtube_follow_pointer_e2e.py / youtube_utterances_e2e.py / youtube_player_controls_e2e.py.

Mapping to the 22 Nov hand-test fixes (orchestrator list): 3 result matched by URL hash despite a hover label rewrite;
4 unparsed Manglish/Malayalam/English go to the YouTube guide (never the generic form stepper); 5 arrow stays on the
title anchor; 6 after scrolling past the choice the pointer says scroll back; 7 hover-preview ads on results are ignored.
Fixes 1, 2 and 8 are voice/panel items: voice_keyterms.py, panel tests (unit.py), voice_english_panel_ml.py.
"""
import json

from _common import result
from _replay import C, Walk, blocked_network, planner, snap
from companion.voice import sarvam

FEATURE = "web-support"
CHECK = "youtube replay: "

# ---- synthetic screens ------------------------------------------------------------------------------
LINK = "Darshana - Official Video Song | Hridayam | Pranav | Merryland 4 minutes, 52 seconds"
HASH = "11aa22bb3"


def search_ui(filled=False, button=True):
    out = [C("search", "AXComboBox", "Search", (357, 135, 491, 24), filled=filled)]
    if button:
        out.append(C("go", "AXButton", "Search", (876, 127, 64, 40)))
    return out


def home(filled=False, ad=False):
    out = search_ui(filled, button=filled)
    if ad:
        out += [C("adc", "AXButton", "My Ad Centre", (1199, 241, 40, 40)), C("spons", "AXStaticText", "Sponsored", (900, 300, 80, 20))]
    return snap(out)


def video(label=LINK, key=HASH, *, title=True, thumb=False, y=320, heading=True, hover=""):
    """One result: title anchor (`a…`), optional thumbnail anchor (`b…`) and the heading YouTube pairs with the title."""
    out = []
    if thumb:
        out.append(C(f"thumb-{key}", "AXLink", label + hover, (160, y - 20, 120, 68), identifier=f"youtube-watch:{key}:bthumb{key[:3]}"))
    if title:
        out.append(C(f"title-{key}", "AXLink", label + hover, (300, y, 500, 30), identifier=f"youtube-watch:{key}:atitle{key[:3]}"))
        if heading:
            out.append(C(f"head-{key}", "AXHeading", label, (300, y, 500, 30)))
    return out


def results(*videos, ads=(), filters=True, below=0):
    out = search_ui(True)
    if filters:
        out.append(C("filters", "AXButton", "Search filters", (1127, 183, 102, 40)))
    for v in videos:
        out += v
    out += list(ads)
    return snap(out, below=below)


def watch(*, playing=True, muted=False, full=False, captions="off", ads=(), menu=(), panel=None, below=0):
    """A watch page. captions: off | on | unavailable. menu: Settings rows (labels). panel: the speed panel's current value."""
    c = [C("seek", "AXSlider", "Seek slider", (91, 549, 883, 8)),
         C("pp", "AXButton", "Pause (k)" if playing else "Play keyboard shortcut k", (91, 563, 40, 41)),
         C("mute", "AXButton", "Unmute (m)" if muted else "Mute (m)", (143, 563, 40, 41)),
         C("cc", "AXCheckBox", "Subtitles/closed captions unavailable" if captions == "unavailable" else "Subtitles/closed captions (c)",
           (638, 563, 48, 41), filled=None if captions == "unavailable" else captions == "on"),
         C("gear", "AXPopUpButton", "Settings", (686, 563, 48, 41)),
         C("fs", "AXButton", "Exit full screen (f)" if full else "Full screen (f)", (830, 563, 48, 41))]
    c += list(ads)
    for i, label in enumerate(menu):
        c.append(C(f"row{i}", "AXMenuItem", label, (679, 223 + 48 * i, 288, 49)))
    if panel is not None:
        c += [C("dec", "AXButton", "Decrease playback speed 0.05", (660, 347, 33, 33)),
              C("spd", "AXSlider", f"Playback speed slider {panel}", (708, 351, 203, 25)),
              C("inc", "AXButton", "Increase playback speed 0.05", (926, 347, 33, 33))]
        c += [C(f"pre{p}", "AXButton", p, (660 + 61 * i, 403, 54, 33)) for i, p in enumerate(("1.0", "1.25", "1.5", "2.0", "3.0"))]
    return snap(c, below=below)


MENU = ("Ambient mode", "Annotations", "Subtitles/CC English", "Sleep timer Off", "Playback speed Normal", "Quality Auto (720p)")
AD_NEAR_BAR = C("adc", "AXButton", "My Ad Centre", (167, 567, 14, 30))
SKIP = C("skip", "AXButton", "Skip", (786, 505, 86, 37))
SCENARIOS = {}


def scenario(fn):
    SCENARIOS[fn.__name__.removeprefix("s_").replace("_", " ")] = fn
    return fn


def intent_provider(action, title=""):
    """MOCK Sarvam chat reply for the one intent call."""
    def reply(payload):
        assert payload["messages"][1]["role"] == "user"
        return {"id": "mock", "choices": [{"finish_reason": "stop",
                                           "message": {"content": json.dumps({"action": action, "title": title})}}]}
    return reply


# ---- Abin's sentences (bug 4) -----------------------------------------------------------------------
SLOW_COUNTDOWN = [(1, 5), (0.95, 4), (0.9, 3), (0.85, 2), (0.8, 1)]


def slow_walk(question):
    w = Walk(question)
    w.step(watch(), "point", "Settings", role="AXPopUpButton", not_text="form")
    w.step(watch(menu=MENU), "point", "Playback speed")
    for value, left in SLOW_COUNTDOWN:
        w.step(watch(menu=MENU, panel=value), "point", "Decrease playback speed", text=f"({left} more time" + ("s" if left > 1 else "")[:1])
    w.step(watch(panel=0.75), "complete", text="0.75")
    return w


@scenario
def s_abin_slow_sentences_use_one_intent_call_then_the_youtube_guide():
    """Bug 4: unparsed Malayalam / English / mixed requests to slow down get ONE intent call, then Settings -> countdown -> 0.75."""
    for q in ("എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം.", "I need to slow down this video.",
              "എനിക്ക് വീഡിയോ ഇച്ചിരി സ്ലോ ആക്കണം / I need to slow down the video a bit"):
        with blocked_network(intent_provider("slower")) as calls:
            slow_walk(q)
            # "a bit" is a local parse (no call); the others take exactly one call and send only the question
            assert len(calls) <= 1, f"{q!r}: {len(calls)} provider calls"
            assert all(c["messages"][1]["content"] == q for c in calls), "the intent call sent more than the question"
    with blocked_network(intent_provider("slower")) as calls:
        slow_walk("എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം.")
        assert len(calls) == 1, f"expected exactly one intent call, got {len(calls)}"


@scenario
def s_local_parses_need_no_provider_call():
    """Sentences the local parse understands (including 'speed it up' and 'I want to watch Darshana.') make no network call."""
    with blocked_network():
        slow_walk("I need to slow down the video a bit")
        for q in ("Enikku darshana kaananam", "I want to watch Darshana."):
            w = Walk(q)
            d = w.step(home(), "point", "Search", text="darshana")
            assert "form" not in d.instruction_en.lower()


@scenario
def s_unparsed_find_sentence_uses_the_mock_intent_and_types_the_title():
    with blocked_network(intent_provider("find", "darshana")) as calls:
        Walk("Enikku darshana kaaranam").step(home(), "point", "Search", text="darshana")
        assert len(calls) == 1


@scenario
def s_provider_failure_degrades_inside_the_youtube_guide_never_the_form_stepper():
    """Bug 4 (loop): if the intent call fails, the YouTube guide still answers and the answer is stable, not a form loop."""
    def fail(payload):
        raise sarvam.SarvamError("mock outage")
    with blocked_network(fail):
        w = Walk("എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം.")
        seen = set()
        for _ in range(5):
            d = w.step(home(), "point", "Search")
            seen.add(d.instruction_en)
            assert "form" not in d.instruction_en.lower() and "Next," not in d.instruction_en
        assert len(seen) == 1, f"the answer changed between identical screens: {seen}"


# ---- search -> result -> play (bugs 3, 5, 6, 7) ------------------------------------------------------
def q1_to_result(w):
    w.step(home(), "point", "Search", text="darshana")
    w.step(snap(search_ui(True)), "point", "Search", role="AXButton")
    d = w.step(results(video(thumb=True, hover=""), video("Darshana cover by someone", "ccc333ccc", y=420),
                       video("Mix – Darshana Rajendran", "ddd444ddd", y=520)), "point", "Darshana - Official")
    return d


@scenario
def s_arrow_stays_on_the_title_anchor():
    """Bug 5: with a thumbnail anchor listed first and a title anchor second, the pointer is on the title and stays there."""
    w = Walk("Find and play Darshana Hridayam")
    q1_to_result(w)
    ctl = w.pl._site_guide.chosen_result
    assert ctl is not None and ctl.title_anchor, "the chosen result is not the title anchor"
    # the title anchor disappears for a moment (only the thumbnail): wait, do not flip to the thumbnail
    w.step(results(video(title=False, thumb=True)), "clarify", text="title")
    d = w.step(results(video(thumb=True)), "point", "Darshana - Official")
    assert w.pl._site_guide.chosen_result.title_anchor


@scenario
def s_hover_label_rewrite_keeps_the_same_video():
    """Bug 3: hovering rewrites the label; the result is matched by its URL hash and the pointer does not get stuck."""
    w = Walk("Find and play Darshana Hridayam")
    q1_to_result(w)
    hovered = results(video(thumb=True, hover=" Now playing preview 0:12"), video("Darshana cover by someone", "ccc333ccc", y=420))
    d = w.step(hovered, "point", "Darshana - Official")
    assert (hovered.control(d.control_id).identifier or "").startswith(f"youtube-watch:{HASH}:a")
    d = w.step(results(video("Darshana - Official Video Song | Hridayam", HASH, thumb=True)), "point", "Darshana - Official")


@scenario
def s_scrolled_past_the_choice_says_scroll_back():
    """Bug 6: after scrolling, only weaker matches are visible; the pointer must not jump to them."""
    w = Walk("Find and play Darshana Hridayam")
    q1_to_result(w)
    # weaker results that DO contain the words ("cover", "reaction" are derivatives): they match, but score lower than the choice
    away = results(video("Darshana Hridayam cover by someone", "eee555eee", y=300), video("Hridayam Darshana reaction", "fff666fff", y=420), below=40)
    d = w.step(away, "clarify", text="scroll back up")
    w.step(results(video(thumb=True), video("Darshana Hridayam cover by someone", "eee555eee", y=420)), "point", "Darshana - Official")


@scenario
def s_hover_preview_ads_on_results_are_ignored():
    """Bug 7: ad markers on a results page (hover preview) must not cause 'The ad will finish' or hide the result."""
    # a hover preview player on the results page: its own Mute control with ad markers right beside it
    ads = [C("pv-mute", "AXButton", "Mute (m)", (310, 350, 40, 40)), C("ad1", "AXStaticText", "Ad 1 of 2", (300, 362, 80, 20)),
           C("adc", "AXButton", "My Ad Centre", (360, 355, 40, 30)), C("ad2", "AXStaticText", "Sponsored", (300, 392, 80, 20))]
    w = Walk("Find and play Darshana Hridayam")
    w.step(home(), "point", "Search")
    w.step(snap(search_ui(True)), "point", "Search", role="AXButton")
    w.step(results(video(thumb=True), ads=ads), "point", "Darshana - Official", not_text="ad will finish")


@scenario
def s_home_display_ad_does_not_block_search():
    w = Walk("Find and play Darshana Hridayam")
    w.step(home(ad=True), "point", "Search", text="darshana", not_text="ad will finish")


@scenario
def s_player_ad_waits_then_skips_then_completes():
    """An ad on the player: wait (non-pointing), point at Skip when it shows, never complete while the ad is up."""
    w = Walk("Find and play Darshana Hridayam")
    q1_to_result(w)
    w.step(watch(ads=[AD_NEAR_BAR]), "clarify", text="ad will finish")
    w.step(watch(ads=[AD_NEAR_BAR, SKIP]), "point", "Skip")
    w.step(watch(), "complete", text="playing")


# ---- player controls ----------------------------------------------------------------------------------
@scenario
def s_pause_and_play():
    with blocked_network():
        w = Walk("pause")
        w.step(watch(playing=True), "point", "Pause")
        w.step(watch(playing=False), "complete", text="paused")
        w = Walk("resume")
        w.step(watch(playing=False), "point", "Play keyboard shortcut k")
        w.step(watch(playing=True), "complete", text="playing")


@scenario
def s_mute_and_unmute():
    with blocked_network():
        w = Walk("mute")
        w.step(watch(), "point", "Mute")
        w.step(watch(muted=True), "complete", text="muted")
        w = Walk("unmute")
        w.step(watch(muted=True), "point", "Unmute")
        w.step(watch(muted=False), "complete", text="sound is on")


@scenario
def s_full_screen_says_press_esc():
    with blocked_network():
        w = Walk("full screen")
        w.step(watch(), "point", "Full screen", text="Esc")
        w.step(watch(full=True), "complete", text="Esc")
        Walk("exit full screen").step(watch(full=True), "clarify", text="Esc")


@scenario
def s_faster_points_at_the_1_25_preset_and_completes():
    with blocked_network():
        w = Walk("speed it up")
        w.step(watch(), "point", "Settings")
        w.step(watch(menu=MENU), "point", "Playback speed")
        w.step(watch(menu=MENU, panel=1), "point", "1.25", text="playback speed")
        w.step(watch(panel=1.25), "complete", text="1.25")
    with blocked_network(intent_provider("faster")) as calls:  # "make it faster" is not a local phrase: one mock call
        w = Walk("make it faster")
        w.step(watch(), "point", "Settings")
        assert len(calls) == 1


@scenario
def s_malayalam_subtitles_are_honest_when_not_available():
    """Unavailable captions or a language list without Malayalam end 'unsupported' (honest), never a pointer to a wrong row."""
    with blocked_network():
        Walk("സബ്ടൈറ്റിൽ ഇടൂ").step(watch(captions="unavailable"), "unsupported", text="unavailable")
        langs = watch(menu=("Off", "Auto-translate", "English (auto-generated)"))
        Walk("malayalam subtitles").step(langs, "unsupported", text="Malayalam")
        w = Walk("malayalam subtitles")
        with_ml = watch(menu=("Off", "Auto-translate", "Malayalam"))
        w.step(with_ml, "point", "Malayalam")
        selected = snap([c if c.label != "Malayalam" else C("row2", "AXMenuItem", "Malayalam", c.frame, filled=True)
                         for c in with_ml.controls])
        w.step(selected, "complete", text="Malayalam subtitles")


# ---- runner -------------------------------------------------------------------------------------------
def run():
    out = []
    for name, fn in SCENARIOS.items():
        try:
            fn()
            out.append(result(FEATURE, CHECK + name, "pass", "automated", f"{fn.__doc__ or ''}".strip()[:140] or "ok"))
        except Exception as exc:  # noqa: BLE001 - a failed assertion is the finding
            out.append(result(FEATURE, CHECK + name, "fail", "automated", f"{type(exc).__name__}: {exc}"[:600]))
    return out
