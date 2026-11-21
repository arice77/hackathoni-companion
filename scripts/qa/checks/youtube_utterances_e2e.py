"""Abin's real utterances through the full YouTube walk (live, Sarvam planner, own Safari window per utterance pair).

Each pair is one run of youtube_follow_pointer_e2e: Q1 finds and plays the song, Q2 slows the video to 0.75 (countdown 5..1) and
the driver puts the speed back to Normal. Sentences the local parse does not know take the planner's one Sarvam intent call
(Abin's hand test, 22 Nov: they used to fall into the generic form stepper and loop).

LIVE + SARVAM, about 15-20 chat calls per pair (3 pairs by default, about 3 minutes). Override with
QA_YT_UTTERANCES='[["Q1 text","Q2 text"], ...]'. BLOCKED unless QA_LIVE_SARVAM=1 (same gates as the base check).
"""
import json
import os
import time

import youtube_follow_pointer_e2e as base

FEATURE = "web-support"
PAIRS = [
    ["Enikku darshana kaananam", "എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം."],
    ["I want to watch Darshana.", "I need to slow down this video."],
    ["ദർശന പാട്ട് പ്ലേ ചെയ്യൂ", "എനിക്ക് വീഡിയോ ഇച്ചിരി സ്ലോ ആക്കണം / I need to slow down the video a bit"],
]


def pairs():
    raw = os.environ.get("QA_YT_UTTERANCES")
    return json.loads(raw) if raw else PAIRS


def run():
    out = []
    saved = (base.QUESTION, base.THEN_ASK)
    try:
        for i, (q1, q2) in enumerate(pairs(), 1):
            base.QUESTION, base.THEN_ASK = q1, q2
            got = base.run()
            blocked = [r for r in got if r["status"] == "blocked"]
            for r in got:
                r = dict(r)
                r["check"] = f"[utterance {i}: {q1[:24]!r} then {q2[:24]!r}] {r['check']}"
                out.append(r)
            if blocked:
                break  # gates (opt-in, key, pack, AX) are the same for every pair
            time.sleep(3)
    finally:
        base.QUESTION, base.THEN_ASK = saved
    return out
