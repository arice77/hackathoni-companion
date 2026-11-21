"""YouTube guidance from visible player controls and one active viewer intent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..contracts import Control, Decision, Snapshot
from . import PrivacyProfile, SitePack, SiteStep, _phrase

_MENU = {"AXMenuItem", "AXMenuItemCheckbox", "AXMenuItemRadio", "AXButton"}
_SEARCH = {"AXComboBox", "AXSearchField", "AXTextField"}
_CC = re.compile(r"^(?:subtitles/closed captions|closed captions|cc)(?:\b|\s|$)")
_SPEED_PRESET = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_VALUE = re.compile(r"(?:(?:playback speed|speed)\s*:?\s*)?(\d+(?:\.\d+)?)\s*[x×]?")
_NAMED_SPEED = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?:\s*[x×]|\s+(?:speed|vegathayil|വേഗത്തിൽ))(?!\w)")
_EXPLICIT_SPEED = re.compile(r"(?:set |change )?(?:playback )?speed (?:to |at )?(\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_CONTEXT = re.compile(r"\b(?:play at|speed|slower|faster|vegathayil)\b|വേഗത്തിൽ")
_MALAYALAM_CHOICE = re.compile(r"(?:malayalam|മലയാളം)(?:\s*\([^)]*\))?")
_POLITE_PREFIX = re.compile(r"^(?:(?:can|could|would) you(?: please)?|please|how (?:do|can) i) ")
_CONTROL_KEYS = {
    "fullscreen": ("full screen", "fullscreen", "go full screen", "bigger screen", "make the video bigger", "make it bigger",
                   "വീഡിയോ വലുതാക്കി കാണണം", "വലുതാക്കി കാണിക്കൂ", "video valuthakkam", "full screen aakkam"),
    "exit_fullscreen": ("exit full screen", "exit fullscreen", "how do i exit full screen",
                        "ഫുൾ സ്ക്രീനിൽ നിന്ന് എങ്ങനെ പുറത്തു വരാം", "full screen engane ozhivakkam"),
    "pause": ("pause", "pause this video", "pause the video", "വീഡിയോ നിർത്തൂ", "video pause cheyyu"),
    "play": ("play", "play this video", "resume the video", "വീഡിയോ വീണ്ടും പ്ലേ ചെയ്യൂ", "video play cheyyu"),
    "mute": ("mute", "mute this video", "mute the sound", "ശബ്ദം ഓഫ് ചെയ്യൂ", "sound mute cheyyu"),
    "unmute": ("unmute", "unmute this video", "turn the sound back on", "ശബ്ദം തിരിച്ചു കൊണ്ടുവരൂ",
               "sound unmute cheyyu"),
    "captions": ("malayalam subtitles", "show malayalam subtitles", "turn on malayalam subtitles",
                 "മലയാളം സബ്ടൈറ്റിൽ വേണം", "മലയാളം സബ്‌ടൈറ്റിൽ വേണം", "malayalam subtitle venam",
                 "malayalam subtitles venam"),
    "slower": ("slower", "play it slower", "slow down", "slow it down", "make it slower", "make the video slower",
               "play this video slower", "വീഡിയോ പതുക്കെ പ്ലേ ചെയ്യൂ", "പതുക്കെ പ്ലേ ചെയ്യൂ", "വേഗം കുറയ്ക്കൂ",
               "വേഗത കുറയ്ക്കൂ", "pathukke", "pathukke play cheyyu", "speed kurakku", "speed kuraykku"),
    "faster": ("faster", "play it faster", "speed up", "make the video faster", "വേഗം കൂട്ടൂ", "speed koottu"),
}
_SHORTCUT = re.compile(r"\s*\([a-z]\)$")
_SEARCH_PATTERNS = (
    re.compile(r"(?:(?:can you|please) )?(?:find(?: and play)?|search(?: for)?|look for|play|show me) (?P<title>.+)"),
    re.compile(r"i (?:want|would like) to (?:watch|hear|find|play|listen to) (?P<title>.+)"),
    re.compile(r"(?:എനിക്ക് )?(?P<title>.+?)\s+(?:കണ്ടെത്തൂ|തിരയൂ|കേൾക്കണം|കാണണം|പ്ലേ ചെയ്യൂ|കാണിക്കൂ)"),
    re.compile(r"(?P<title>.+?)\s+(?:play cheyyu|search cheyyu|thirayoo|kaanam|kelkkanam)"),
)
_TITLE_PREFIX = re.compile(r"^(?:the|a|an|please|(?:song|video) (?:called|named)|ഒന്ന്|യൂട്യൂബിൽ)\s+")
_TITLE_SUFFIX = re.compile(r"\s+(?:on youtube|song|video|paattu|പാട്ട്|വീഡിയോ|please|ഒന്ന്|എന്ന)$")
_GENERIC_TITLE = {
    "", "a", "a song", "a video", "music", "something", "song", "video", "a malayalam", "malayalam",
    "പാട്ട്", "വീഡിയോ", "paattu", "oru paattu",
}
_TOKENS = re.compile(r"(?:[^\W_]|[\u0d00-\u0d03\u0d3b-\u0d4d\u0d57\u200c\u200d])+", re.UNICODE)
_ROMAN_NAMES = {"ദർശന": "darshana", "ദര്‍ശന": "darshana", "ഹൃദയം": "hridayam"}
_PLAYER = (
    ("AXButton", "Play (k)"), ("AXButton", "Pause (k)"), ("AXButton", "Mute (m)"),
    ("AXButton", "Unmute (m)"), ("AXButton", "Full screen (f)"), ("AXButton", "Exit full screen (f)"),
    ("AXPopUpButton", "Settings"), ("AXCheckBox", "Subtitles/closed captions (c)"),
    ("AXCheckBox", "Subtitles/closed captions unavailable"), ("AXButton", "Skip ad"),
)
_VIDEO_LINK_PREFIX = "youtube-watch:"


@dataclass(frozen=True)
class Intent:
    action: str
    titles: tuple[str, ...] = ()
    speed: Decimal | None = None


def parse_intent(question: str) -> Intent | None:
    parts = tuple(_POLITE_PREFIX.sub("", _phrase(part)) for part in question.split(" / ", 1))
    for part in parts:
        rate = _EXPLICIT_SPEED.fullmatch(part)
        if rate is None and _SPEED_CONTEXT.search(part):
            rate = _NAMED_SPEED.search(part)
        if rate is None and ("." in part or part.endswith(("x", "×"))):
            rate = _SPEED_PRESET.fullmatch(part)
        if rate:
            return Intent("speed", speed=Decimal(rate.group(1)))
        for action, phrases in _CONTROL_KEYS.items():
            if part in phrases:
                if action in {"slower", "faster"}:
                    return Intent("speed", speed=Decimal("0.75") if action == "slower" else None)
                return Intent(action)
    titles = []
    for part in parts:
        for pattern in _SEARCH_PATTERNS:
            match = pattern.fullmatch(part)
            if match:
                title = match["title"]
                previous = ""
                while previous != title:
                    previous = title
                    title = _TITLE_PREFIX.sub("", title.strip(' "\'“”‘’'))
                    title = _TITLE_SUFFIX.sub("", title).strip(' "\'“”‘’')
                titles.append(title)
                break
    return Intent("find", tuple(dict.fromkeys(t for t in titles if t not in _GENERIC_TITLE))) if titles else None


def _key(control: Control) -> tuple[str, str]:
    return control.role, _phrase(control.label)


def _rank(control: Control) -> tuple[float, float]:
    return control.frame[1], control.frame[0]


def _target(controls: tuple[Control, ...], roles: set[str], label: str) -> Control | None:
    return next((
        c for c in controls if c.enabled and c.role in roles and _SHORTCUT.sub("", _phrase(c.label)) == label
    ), None)


def _menu(controls: tuple[Control, ...], label: str) -> Control | None:
    head = re.compile(rf"^{re.escape(label)}(?=$|[\s:(])")
    return next((c for c in controls if c.enabled and c.role in _MENU and head.search(_phrase(c.label))), None)


def _decision(snap: Snapshot, kind: str, ml: str, en: str) -> Decision:
    return Decision(kind, snap.snapshot_id, ml, en, source="sarvam")


def _point(snap: Snapshot, control: Control, ml: str, en: str) -> Decision:
    label = f"‘{control.label}’"
    return Decision("point", snap.snapshot_id, ml.format(label=label), en.format(label=label), control.id, "sarvam")


def _title_words(label: str) -> set[str]:
    return {_ROMAN_NAMES.get(word, word) for word in _TOKENS.findall(_phrase(label))}


def _video_key(control: Control) -> str:
    if control.identifier and control.identifier.startswith(_VIDEO_LINK_PREFIX):
        return control.identifier.removeprefix(_VIDEO_LINK_PREFIX).split(":", 1)[0]
    return ""


def _result_links(controls: tuple[Control, ...]) -> tuple[Control, ...]:
    # Channel cards also have both a heading and a link. Only the reader can verify a watch URL.
    titles = {_phrase(c.label) for c in controls if c.role == "AXHeading" and c.label}
    links = {}
    for c in controls:
        if c.role != "AXLink" or not c.enabled or not c.label or not (key := _video_key(c)):
            continue
        earlier = links.get(key)
        if earlier is None or (_phrase(earlier.label) not in titles and _phrase(c.label) in titles):
            links[key] = c
    return tuple(links.values())


def _best_result(links: tuple[Control, ...], titles: tuple[str, ...]) -> Control | None:
    if not titles:
        return links[0] if links else None
    matches = []
    for link in links:
        label, words = _phrase(link.label), _title_words(link.label)
        for title in titles:
            wanted = _title_words(title)
            if wanted and wanted <= words:
                matches.append(((label == title, title in label, len(wanted), -len(words)), link))
    return max(matches, key=lambda row: row[0])[1] if matches else None


def _settings(snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
    if gear := _target(controls, {"AXPopUpButton", "AXButton"}, "settings"):
        return _point(snap, gear, "{label} അമർത്തൂ.", "Open {label}.")
    return _decision(
        snap, "clarify", "ആദ്യം വീഡിയോ തുറക്കൂ. അപ്പോൾ താഴെ ⚙ Settings കാണാം.",
        "Open a video first. Then look for Settings at the bottom of the player.",
    )


def _ad(snap: Snapshot, controls: tuple[Control, ...]) -> Decision | None:
    skip = _target(controls, {"AXButton"}, "skip ad") or _target(controls, {"AXButton"}, "skip ads")
    if skip is not None:
        return _point(snap, skip, "പരസ്യം ഒഴിവാക്കാൻ {label} അമർത്തൂ.", "Use {label} to skip the ad.")
    if any(
        re.fullmatch(r"skip ads?(?: in .+)?|ad \d+ of \d+|ad will end in .+|video will play after ad", _phrase(c.label))
        for c in controls
    ):
        return _decision(snap, "clarify", "പരസ്യം തീരുന്നതുവരെ ഒന്ന് കാത്തിരിക്കൂ.",
                         "Wait for the ad to finish.")
    return None


@dataclass
class YouTubeGuide:
    intent: Intent
    search_phase: str = "start"
    prior_results: tuple[tuple[str, str], ...] = ()
    result_label: str | None = None
    replacing_search: bool = False
    had_player: bool = False
    last_key: tuple[str, str] | None = None

    def decide(self, snap: Snapshot) -> Decision:
        controls = tuple(sorted(snap.controls, key=_rank))
        if self.intent.action == "exit_fullscreen":
            return _decision(snap, "clarify", "ഫുൾ സ്ക്രീനിൽ നിന്ന് പുറത്തുവരാൻ Esc അമർത്തൂ.",
                             "Press Esc to leave full screen.")
        if ad := _ad(snap, controls):
            return ad
        if self.intent.action == "find":
            decision = self._find(snap, controls)
        elif self.intent.action == "speed":
            decision = self._speed(snap, controls)
        elif self.intent.action == "captions":
            decision = self._captions(snap, controls)
        else:
            decision = self._player(snap, controls)
        if decision.control_id is not None and (target := snap.control(decision.control_id)) is not None:
            self.last_key = _key(target)
        return decision

    def _find(self, snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
        search = _target(controls, _SEARCH, "search")
        submit = _target(controls, {"AXButton"}, "search")
        links = _result_links(controls)
        fingerprint = tuple((c.role, _video_key(c)) for c in links)
        result = _best_result(links, self.intent.titles)
        play = _target(controls, {"AXButton"}, "play")
        pause = _target(controls, {"AXButton"}, "pause")
        results_ui = any(
            c.role in {"AXButton", "AXHeading", "AXPopUpButton"}
            and _phrase(c.label) in {"filters", "search filters", "search results"}
            for c in controls
        )
        if self.search_phase == "watch":
            on_watch = (play is not None or pause is not None) and (
                not self.had_player or fingerprint != self.prior_results
            )
            if on_watch and pause is not None:
                return _decision(snap, "complete", "വീഡിയോ ഇപ്പോൾ പ്ലേ ചെയ്യുന്നു.", "The video is playing.")
            if on_watch and play is not None:
                return _point(snap, play, "വീഡിയോ തുടങ്ങാൻ {label} അമർത്തൂ.", "Use {label} to start the video.")
            if result is not None and _phrase(result.label) == self.result_label:
                return _point(snap, result, "വീഡിയോ കാണാൻ {label} അമർത്തൂ.", "Open {label} to play the video.")
        elif self.search_phase == "start":
            if play is None and pause is None and (results_ui or (links and search and search.filled is True)):
                self.search_phase = "results"
            elif search is not None:
                self.search_phase, self.prior_results = "typing", fingerprint
                self.replacing_search = search.filled is True
        if self.search_phase == "typing" and search is not None:
            if fingerprint != self.prior_results and links and play is None and pause is None:
                self.search_phase = "results"
            elif search.filled is True and not self.replacing_search and submit is not None:
                self.search_phase = "submitted"
                return _point(snap, submit, "തിരയാൻ {label} അമർത്തൂ.", "Click {label} to see the results.")
            else:
                return self._type_into(snap, search)
        if self.search_phase == "submitted":
            if results_ui or fingerprint != self.prior_results:
                self.search_phase = "results"
            elif submit is not None:
                return _point(snap, submit, "തിരയാൻ {label} അമർത്തൂ.", "Click {label} to see the results.")
        if result is not None and (self.search_phase != "watch" or self.result_label == _phrase(result.label)):
            self.search_phase, self.result_label, self.prior_results = "watch", _phrase(result.label), fingerprint
            self.had_player = play is not None or pause is not None
            return _point(snap, result, "വീഡിയോ കാണാൻ {label} അമർത്തൂ.", "Open {label} to play the video.")
        if self.search_phase in {"results", "watch"} and snap.below_fold_count > 0:
            return _decision(snap, "clarify", "കൂടുതൽ ഫലങ്ങൾ കാണാൻ താഴേക്ക് സ്ക്രോൾ ചെയ്യൂ.",
                             "Scroll down to see more results.")
        if self.search_phase == "results":
            if self.intent.titles:
                return _decision(
                    snap, "clarify", "ചോദിച്ച വീഡിയോ കാണുന്നില്ല. പേര് നോക്കി വീണ്ടും തിരയൂ.",
                    "I don’t see a result with that name. Check the name and search again.",
                )
            return _decision(snap, "clarify", "വീഡിയോ ഒന്നും കാണുന്നില്ല. വേറൊരു പേര് കൊടുത്ത് തിരയൂ.",
                             "I don’t see a video here. Try searching with another name.")
        if search is not None and self.search_phase == "start":
            self.search_phase, self.prior_results = "typing", fingerprint
            self.replacing_search = search.filled is True
            return self._type_into(snap, search)
        return _decision(snap, "clarify", "തിരച്ചിൽ ഫലം വരുന്നതുവരെ ഒന്ന് കാത്തിരിക്കൂ.",
                         "Wait for YouTube to show the search results or video.")

    def _type_into(self, snap: Snapshot, search: Control) -> Decision:
        if self.intent.titles:
            title = self.intent.titles[0]
            ml = f"‘{title}’ എന്ന പേര് ‘{search.label}’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ."
            en = f"Type ‘{title}’ in ‘{search.label}’."
        else:
            ml, en = f"കാണേണ്ട പാട്ടിന്റെയോ വീഡിയോയുടെയോ പേര് ‘{search.label}’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ.", (
                f"Type the name of a song or video you want to watch in ‘{search.label}’."
            )
        if self.replacing_search:
            ml += " അവിടെയുള്ള പഴയ പേര് മാറ്റിയിട്ട് Return അമർത്തൂ."
            en += " Replace the old search text and press Return."
        return Decision("point", snap.snapshot_id, ml, en, search.id, "sarvam")

    def _player(self, snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
        action = self.intent.action
        labels = {
            "fullscreen": ("full screen", "exit full screen", "സ്ക്രീൻ വലുതാക്കാൻ {label} അമർത്തൂ. പുറത്തുവരാൻ Esc അമർത്താം.",
                           "Click {label} for a bigger picture. Press Esc to exit.",
                           "വീഡിയോ ഫുൾ സ്ക്രീനിലാണ്. പുറത്തുവരാൻ Esc അമർത്താം.", "Full screen is on. Press Esc to exit."),
            "pause": ("pause", "play", "വീഡിയോ നിർത്തിവയ്ക്കാൻ {label} അമർത്തൂ.", "Click {label} to pause the video.",
                      "വീഡിയോ നിർത്തിവച്ചിട്ടുണ്ട്.", "The video is paused."),
            "play": ("play", "pause", "വീഡിയോ തുടരാൻ {label} അമർത്തൂ.", "Click {label} to play the video.",
                     "വീഡിയോ പ്ലേ ചെയ്യുന്നു.", "The video is playing."),
            "mute": ("mute", "unmute", "ശബ്ദം നിർത്താൻ {label} അമർത്തൂ.", "Click {label} to mute the sound.",
                     "ശബ്ദം മ്യൂട്ടാണ്.", "The sound is muted."),
            "unmute": ("unmute", "mute", "ശബ്ദം കേൾക്കാൻ {label} അമർത്തൂ.", "Click {label} to turn the sound back on.",
                       "വീഡിയോയുടെ ശബ്ദം ഓണാണ്.", "The video sound is on."),
        }
        wanted, done, ml, en, ml_done, en_done = labels[action]
        if target := _target(controls, {"AXButton"}, wanted):
            return _point(snap, target, ml, en)
        if _target(controls, {"AXButton"}, done):
            return _decision(snap, "complete", ml_done, en_done)
        return _decision(snap, "clarify", "ആദ്യം വീഡിയോ തുറക്കൂ. താഴെയുള്ള ബട്ടണുകൾ അപ്പോൾ കാണാം.",
                         "Open a video first so the player controls are visible.")

    def _speed(self, snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
        rates = []
        for c in controls:
            if c.role in _MENU and c.enabled and (value := _SPEED_PRESET.fullmatch(_phrase(c.label))):
                rates.append((Decimal(value[1]), c))
        requested = self.intent.speed
        if rates:
            if requested is None:
                faster = ", ".join(str(rate) for rate, _ in rates if rate > 1)
                return _decision(
                    snap, "clarify", f"കൂടുതൽ വേഗം എത്ര വേണം? കാണുന്ന ഓപ്ഷനുകൾ {faster or 'ഇല്ല'}.",
                    f"How fast would you like it? Visible faster options are {faster or 'unavailable'}.",
                )
            if target := next((c for rate, c in rates if rate == requested), None):
                if target.filled is True:
                    return _decision(snap, "complete", f"വീഡിയോ {requested} മടങ്ങ് വേഗത്തിലാണ്.",
                                     f"The video is set to {requested}×.")
                return _point(snap, target, "വേഗം മാറ്റാൻ {label} അമർത്തൂ.", "Choose {label} for that playback speed.")
            return _decision(
                snap, "clarify", f"പട്ടികയിൽ {requested} കാണാൻ ഒന്ന് സ്ക്രോൾ ചെയ്യൂ.",
                f"Scroll inside Playback speed to look for {requested}×.",
            )
        if speed := _menu(controls, "playback speed"):
            value = _SPEED_VALUE.fullmatch(_phrase(speed.label))
            if requested is not None and value is not None and Decimal(value[1]) == requested:
                return _decision(snap, "complete", f"വീഡിയോ {requested} മടങ്ങ് വേഗത്തിലാണ്.",
                                 f"The video is set to {requested}×.")
            return _point(snap, speed, "വീഡിയോയുടെ വേഗം മാറ്റാൻ {label} തുറക്കൂ.",
                          "Open {label} to see the available speeds.")
        if self.last_key is not None and _SPEED_PRESET.fullmatch(self.last_key[1]):
            return _decision(snap, "clarify", "വേഗം മാറിയോ എന്ന് വീഡിയോ നോക്കി ഉറപ്പാക്കൂ.",
                             "Check that the video is playing at the speed you chose.")
        return _settings(snap, controls)

    def _captions(self, snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
        cc = next((c for c in controls if c.role in {"AXCheckBox", "AXButton"} and _CC.search(_phrase(c.label))), None)
        if cc is not None and "unavailable" in _phrase(cc.label):
            return _decision(
                snap, "unsupported", "ഈ വീഡിയോയ്ക്ക് സബ്‌ടൈറ്റിൽ ലഭ്യമല്ല.",
                "Subtitles are unavailable for this video.",
            )
        language_list = any(
            c.role in _MENU and _phrase(c.label) in {"off", "auto-translate", "auto translate"}
            for c in controls
        )
        requested_menu = self.last_key is not None and self.last_key[1].startswith("subtitles/cc")
        malayalam = next((
            c for c in controls if c.role in _MENU and c.enabled
            and (language_list or requested_menu) and _MALAYALAM_CHOICE.fullmatch(_phrase(c.label))
        ), None)
        if malayalam is not None:
            if malayalam.filled is True:
                return _decision(snap, "complete", "മലയാളം സബ്‌ടൈറ്റിൽ ഓണാണ്.", "Malayalam subtitles are selected.")
            return _point(snap, malayalam, "മലയാളം സബ്‌ടൈറ്റിലിന് {label} തിരഞ്ഞെടുക്കൂ.",
                          "Choose {label} for Malayalam subtitles.")
        caption_menu = _menu(controls, "subtitles/cc")
        if language_list:
            return _decision(
                snap, "unsupported", "ഈ വീഡിയോയുടെ സബ്‌ടൈറ്റിൽ പട്ടികയിൽ മലയാളം കാണുന്നില്ല.",
                "Malayalam isn’t listed in this video’s subtitle options.",
            )
        if caption_menu is not None:
            return _point(snap, caption_menu, "ഭാഷകൾ കാണാൻ {label} തുറക്കൂ.", "Open {label} to see the languages.")
        if self.last_key is not None and _MALAYALAM_CHOICE.fullmatch(self.last_key[1]):
            return _decision(snap, "clarify", "മലയാളം സബ്‌ടൈറ്റിൽ കാണുന്നുണ്ടോ എന്ന് നോക്കൂ.",
                             "Check the video for Malayalam subtitles.")
        if cc is not None and cc.enabled and cc.filled is False:
            return _point(snap, cc, "സബ്‌ടൈറ്റിൽ ഓണാക്കാൻ {label} അമർത്തൂ.", "Click {label} to turn on captions.")
        return _settings(snap, controls)


class YouTubePack(SitePack):
    provider_goal = "Guide YouTube search or visible player controls. The user decides what to watch."

    def is_practice(self, snap: Snapshot) -> bool:
        return False

    def start_guidance(self, question: str) -> YouTubeGuide | None:
        intent = parse_intent(question)
        return YouTubeGuide(intent) if intent is not None else None


PACK = YouTubePack(
    name="YouTube",
    hosts=frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"}),
    practice_heading="",
    goals=(),
    entry=SiteStep("AXComboBox", "Search", "വീഡിയോയുടെ പേര് ‘Search’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ.",
                   "Type the video name in ‘Search’."),
    steps=(),
    privacy=PrivacyProfile(frozenset((role, _phrase(label)) for role, label in (
        *_PLAYER, *((role, "Search") for role in {*_SEARCH, "AXButton"}),
        *((role, label) for role in _MENU for label in ("Playback speed", "Subtitles/CC", "Malayalam")),
    ))),
    practice_result="",
)
