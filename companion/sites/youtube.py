"""YouTube guidance from visible player controls and one active viewer intent."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from time import monotonic

from ..contracts import Control, Decision, Snapshot
from . import PrivacyProfile, SitePack, SiteStep, _phrase

_MENU = {"AXMenuItem", "AXMenuItemCheckbox", "AXMenuItemRadio", "AXButton"}
_SETTINGS_ROLES = _MENU | {"AXMenuButton", "AXPopUpButton"}
_SHARED_SETTINGS = ("Playback speed", "Subtitles/CC", "Quality")
_SETTINGS_NAMES = {_phrase(label): label for label in (*_SHARED_SETTINGS, "Ambient mode", "Annotations", "Sleep timer")}
_SETTINGS_ROW = re.compile(rf"^({'|'.join(map(re.escape, _SETTINGS_NAMES))})(?=$|[\s:(])")
_SETTINGS_RETRY_S = 3.0
_SEARCH = {"AXComboBox", "AXSearchField", "AXTextField"}
_CC = re.compile(r"^(?:subtitles/closed captions|closed captions|cc)(?:\b|\s|$)")
_SPEED_PRESET = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_VALUE = re.compile(r"(?:(?:playback speed|speed)\s*:?\s*)?(\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_SLIDER = re.compile(r"playback speed slider (\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_STEP = Decimal("0.05")
_SPEED_TOLERANCE = Decimal("0.001")
_NAMED_SPEED = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?:\s*[x×]|\s+(?:speed|vegathayil|വേഗത്തിൽ))(?!\w)")
_EXPLICIT_SPEED = re.compile(r"(?:set |change )?(?:playback )?speed (?:to |at )?(\d+(?:\.\d+)?)\s*[x×]?")
_SPEED_CONTEXT = re.compile(r"\b(?:play at|speed|slower|faster|vegathayil)\b|വേഗത്തിൽ")
_MALAYALAM_CHOICE = re.compile(r"(?:malayalam|മലയാളം)(?:\s*\([^)]*\))?")
_POLITE_PREFIX = re.compile(r"^(?:(?:can|could|would) you(?: please)?|please|how (?:do|can) i) ")
_COMMAND_PUNCTUATION = str.maketrans({"\u200c": None, "\u200d": None,
                                      **dict.fromkeys(",:;…\"“”‘’-–—", " ")})
_CONTROL_KEYS = {
    "fullscreen": ("full screen", "fullscreen", "go full screen", "bigger screen", "make the video bigger", "make it bigger",
                   "വീഡിയോ വലുതാക്കി കാണണം", "വലുതാക്കി കാണിക്കൂ", "വലുതാക്കൂ", "video valuthakkam",
                   "full screen aakkam", "full screen ആക്കൂ"),
    "exit_fullscreen": ("exit full screen", "exit fullscreen", "how do i exit full screen",
                        "ഫുൾ സ്ക്രീനിൽ നിന്ന് എങ്ങനെ പുറത്തു വരാം", "full screen engane ozhivakkam"),
    "pause": ("pause", "pause this video", "pause the video", "നിർത്തൂ", "വീഡിയോ നിർത്തൂ", "video pause cheyyu"),
    "play": ("play", "play this video", "resume", "resume the video", "പ്ലേ ചെയ്യൂ", "വീഡിയോ വീണ്ടും പ്ലേ ചെയ്യൂ",
             "video play cheyyu"),
    "mute": ("mute", "mute this video", "mute the sound", "ശബ്ദം ഓഫ് ചെയ്യൂ", "sound mute cheyyu"),
    "unmute": ("unmute", "unmute this video", "turn the sound back on", "ശബ്ദം തിരിച്ചു കൊണ്ടുവരൂ",
               "sound unmute cheyyu"),
    "captions": ("subtitles", "show captions", "malayalam subtitles", "show malayalam subtitles",
                 "turn on malayalam subtitles", "മലയാളം സബ്ടൈറ്റിൽ", "മലയാളം സബ്ടൈറ്റിൽ വേണം", "സബ്ടൈറ്റിൽ ഇടൂ",
                 "അക്ഷരങ്ങൾ കാണിക്കൂ", "malayalam subtitle venam", "malayalam subtitles venam"),
    "slower": ("slower", "play it slower", "slow down", "slow it down", "make it slower", "make the video slower",
               "play this video slower", "play slowly", "reduce the speed", "too fast", "വീഡിയോ പതുക്കെ പ്ലേ ചെയ്യൂ",
               "പതുക്കെ പ്ലേ ചെയ്യൂ", "പതുക്കെ", "പതുക്കെ ആക്കൂ", "വേഗം കുറയ്ക്കൂ", "സ്പീഡ് കുറയ്ക്കൂ", "വേഗത കുറയ്ക്കൂ",
               "സാവധാനം", "slow ആക്കൂ", "pathukke", "pathukke play cheyyu", "speed kurakku", "speed kuraykku"),
    "faster": ("faster", "play it faster", "speed up", "speed it up", "make the video faster", "വേഗം കൂട്ടൂ", "speed koottu"),
}
_SPEED_DEFAULTS = {"slower": Decimal("0.75"), "faster": Decimal("1.25")}
_SHORTCUT = re.compile(r"(?:\s*\([a-z]\)|\s+keyboard shortcut\s+[a-z])$")
_SEARCH_PATTERNS = (
    re.compile(r"(?:(?:can you|please) )?(?:find(?: and play)?|search(?: for)?|look for|play|show me) (?P<title>.+)"),
    re.compile(r"i (?:want|would like) to (?:watch|hear|find|play|listen to) (?P<title>.+)"),
    re.compile(r"(?:എനിക്ക് )?(?P<title>.+?)\s+(?:കണ്ടെത്തൂ|തിരയൂ|കേൾക്കണം|കാണണം|പ്ലേ ചെയ്യൂ|കാണിക്കൂ)"),
    re.compile(r"(?P<title>.+?)\s+(?:play cheyyu|search cheyyu|thirayoo|kaanam|kelkkanam)"),
)
_TITLE_PREFIX = re.compile(r"^(?:the|a|an|please|(?:song|video) (?:called|named)|ഒന്ന്|യൂട്യൂബിൽ)\s+")
_TITLE_SUFFIX = re.compile(r"\s+(?:on youtube|please|ഒന്ന്|എന്ന)$")
_MEDIA_SUFFIX = re.compile(r"\s+(?:song|video|paattu|പാട്ട്|വീഡിയോ)$")
_GENERIC_TITLE = {
    "", "a", "a song", "a video", "music", "something", "song", "video", "a malayalam", "malayalam",
    "പാട്ട്", "വീഡിയോ", "paattu", "oru paattu",
}
_TOKENS = re.compile(r"(?:[^\W_]|[\u0d00-\u0d03\u0d3b-\u0d4d\u0d57\u200c\u200d])+", re.UNICODE)
_ROMAN_NAMES = {"ദർശന": "darshana", "ദര്‍ശന": "darshana", "ഹൃദയം": "hridayam"}
_QUERY_ALIASES = {**_ROMAN_NAMES, "പാട്ട്": "song", "paattu": "song", "വീഡിയോ": "video"}
_MALAYALAM = re.compile(r"[\u0d00-\u0d7f]")
_RESULT_SIGNALS = {"song", "official", "video"}
_COLLECTION = re.compile(r"^mix\s*[-–—:]|\bplaylists?\b|\bshorts\b")
_PLAYER_SHORTCUTS = {
    "play": "k", "pause": "k", "mute": "m", "unmute": "m", "full screen": "f", "exit full screen": "f",
}
_CC_LABEL = "subtitles/closed captions"
_SKIP_LABELS = ("skip ad", "skip ads", "skip")
_AD_SKIP_BUTTONS = {("AXButton", label) for label in _SKIP_LABELS}
_AD_MARKERS = {
    "Ad break": re.compile(r"\bad break\b|\bad \d+ of\b|\bad will end in\b|\bvideo will play after ad\b"),
    "My Ad Centre": re.compile(r"\bmy ad cent(?:re|er)\b"),
    "Visit advertiser": re.compile(r"\bvisit advertiser\b"),
    "Ad": re.compile(r"^ad$|\bad\s*·"),
    "Sponsored": re.compile(r"\bsponsored\b"),
    "Skip ad": re.compile(r"^skip(?: ads?)?(?: in .+)?$"),
}
_AD_HEADING = re.compile(r"ad|sponsored|ad \d+ of \d+")
_PLAYER = {
    *(("AXButton", label) for label in _PLAYER_SHORTCUTS),
    ("AXPopUpButton", "settings"), ("AXButton", "settings"),
    ("AXCheckBox", _CC_LABEL), ("AXCheckBox", f"{_CC_LABEL} unavailable"),
    ("AXSlider", "seek slider"), ("AXSlider", "volume"),
}
_PLAYER_SHORTCUT_LABELS = {
    (role, variant)
    for role, label, key in (
        *(("AXButton", label, key) for label, key in _PLAYER_SHORTCUTS.items()),
        ("AXCheckBox", _CC_LABEL, "c"),
    )
    for variant in (f"{label} ({key})", f"{label} keyboard shortcut {key}")
}
_VIDEO_LINK_PREFIX = "youtube-watch:"


@dataclass(frozen=True)
class Intent:
    action: str
    titles: tuple[str, ...] = ()
    speed: Decimal | None = None


def _command_phrase(text: str) -> str:
    # Normalize short commands independently of the text used as a video title.
    phrase = _phrase(text.replace("ല്‍", "ൽ").replace("ര്‍", "ർ").translate(_COMMAND_PUNCTUATION))
    return _POLITE_PREFIX.sub("", phrase).removesuffix(" please")


def parse_intent(question: str) -> Intent | None:
    parts = tuple(_POLITE_PREFIX.sub("", _phrase(part)) for part in question.split(" / ", 1))
    for part in map(_command_phrase, parts):
        rate = _EXPLICIT_SPEED.fullmatch(part)
        if rate is None and _SPEED_CONTEXT.search(part):
            rate = _NAMED_SPEED.search(part)
        if rate is None and ("." in part or part.endswith(("x", "×"))):
            rate = _SPEED_PRESET.fullmatch(part)
        if rate:
            return Intent("speed", speed=Decimal(rate.group(1)))
        for action, phrases in _CONTROL_KEYS.items():
            if part in phrases:
                if action in _SPEED_DEFAULTS:
                    return Intent("speed", speed=_SPEED_DEFAULTS[action])
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
    if not titles:
        # A familiar title with a media word also works as a short Malayalam request.
        titles = [part for part in parts if _MEDIA_SUFFIX.sub("", part) in _ROMAN_NAMES]
    if not titles:
        return None
    return Intent("find", tuple(dict.fromkeys(
        title for title in titles if _MEDIA_SUFFIX.sub("", title) not in _GENERIC_TITLE
    )))


def _player_label(label: str) -> str:
    return _SHORTCUT.sub("", _phrase(label))


def _key(control: Control) -> tuple[str, str]:
    return control.role, _player_label(control.label)


def _rank(control: Control) -> tuple[float, float]:
    return control.frame[1], control.frame[0]


def _target(controls: tuple[Control, ...], roles: set[str], label: str) -> Control | None:
    return next((
        c for c in controls if c.enabled and c.role in roles and _player_label(c.label) == label
    ), None)


def _has_player(controls: tuple[Control, ...]) -> bool:
    return any(_key(c) in _PLAYER for c in controls)


def _await_player(snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
    if _has_player(controls):
        return _decision(snap, "clarify", "ബട്ടണുകൾ കാണാൻ മൗസ് വീഡിയോയുടെ മുകളിലേക്ക് നീക്കൂ.",
                         "Move the pointer over the video to show its controls.")
    return _decision(snap, "clarify", "വീഡിയോയുടെ ബട്ടണുകൾ കാണാൻ ഒന്ന് കാത്തിരിക്കൂ.",
                     "Waiting for YouTube’s player controls.")


def _setting_name(control: Control) -> str | None:
    if control.role in _SETTINGS_ROLES and (match := _SETTINGS_ROW.match(_phrase(control.label))):
        return _SETTINGS_NAMES[match[1]]
    return None


def _menu(controls: tuple[Control, ...], label: str) -> Control | None:
    return next((c for c in controls if c.enabled and _setting_name(c) == label), None)


def _decision(snap: Snapshot, kind: str, ml: str, en: str) -> Decision:
    return Decision(kind, snap.snapshot_id, ml, en, source="sarvam")


def _point(snap: Snapshot, control: Control, ml: str, en: str) -> Decision:
    label = f"‘{control.label}’"
    return Decision("point", snap.snapshot_id, ml.format(label=label), en.format(label=label), control.id, "sarvam")


def _speed_complete(snap: Snapshot, requested: Decimal) -> Decision:
    return _decision(snap, "complete", f"വീഡിയോ {requested} മടങ്ങ് വേഗത്തിലാണ്.",
                     f"The video is set to {requested}×.")


def _adjust_speed(snap: Snapshot, requested: Decimal, current: Decimal | None,
                  decrease: Control | None, increase: Control | None) -> Decision:
    if current is None and requested == 1:
        return _decision(snap, "clarify", "ഇപ്പോഴത്തെ സ്പീഡ് നോക്കി 1× ആക്കൂ.",
                         "Check the current speed and adjust it to 1×.")
    slower = requested < (current if current is not None else 1)
    button = decrease if slower else increase
    if button is None:
        return _decision(snap, "clarify", f"സ്പീഡ് {requested}× ആക്കാനുള്ള ബട്ടൺ ഇപ്പോൾ കാണുന്നില്ല.",
                         f"The button to reach {requested}× isn’t available in this menu.")
    symbol = "−" if slower else "+"
    if current is None:
        return Decision("point", snap.snapshot_id, f"{requested}× കാണുന്നതുവരെ {symbol} അമർത്തൂ.",
                        f"Press {symbol} until it shows {requested}×.", button.id, "sarvam")
    distance = abs(requested - current)
    presses = round(distance / _SPEED_STEP)
    if abs(distance - presses * _SPEED_STEP) > _SPEED_TOLERANCE:
        return _decision(snap, "clarify", "ഈ ബട്ടണുകൾ 0.05× വീതമാണ് സ്പീഡ് മാറ്റുന്നത്. വേറൊരു സ്പീഡ് പറയൂ.",
                         "These buttons change speed by 0.05× at a time. Choose a speed they can reach.")
    ml = "വേഗം കുറയ്ക്കാൻ" if slower else "വേഗം കൂട്ടാൻ"
    en = "slow down" if slower else "speed up"
    times = "time" if presses == 1 else "times"
    return Decision("point", snap.snapshot_id, f"{ml} {symbol} അമർത്തൂ (ഇനി {presses} തവണ)",
                    f"Press {symbol} to {en} ({presses} more {times})", button.id, "sarvam")


def _title_words(label: str) -> set[str]:
    return {_QUERY_ALIASES.get(word, word) for word in _TOKENS.findall(_phrase(label))}


def _search_query(title: str) -> str:
    words = title.split()
    if any(_MALAYALAM.search(word) and word not in _QUERY_ALIASES for word in words):
        return title
    return " ".join(_QUERY_ALIASES.get(word, word) for word in words)


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
        return min(links, key=lambda link: bool(_COLLECTION.search(_phrase(link.label))), default=None)
    queries = [(_title_words(_MEDIA_SUFFIX.sub("", title)), _title_words(title)) for title in titles]
    matches = []
    for link in links:
        label, words = _phrase(link.label), _title_words(link.label)
        for wanted, query in queries:
            if wanted and wanted <= words:
                score = (not _COLLECTION.search(label), len(wanted), query <= words,
                         len(_RESULT_SIGNALS & words), len(query), -len(words))
                matches.append((score, link))
    return max(matches, key=lambda row: row[0])[1] if matches else None


def ad_marker_name(label: str) -> str | None:
    """Identify an ad marker and discard its advertiser name or status text."""
    label = _player_label(label)
    return next((name for name, pattern in _AD_MARKERS.items() if pattern.search(label)), None)


def _ad_marker(control: Control) -> str | None:
    if control.identifier and control.identifier.startswith(
        ("youtube-watch:", "youtube-short:", "youtube-channel:", "youtube-playlist:")
    ):
        return None  # A search result title can contain ad-related words.
    if control.role == "AXHeading" and not _AD_HEADING.fullmatch(_phrase(control.label)):
        return None
    return ad_marker_name(control.label)


def _ad(snap: Snapshot, controls: tuple[Control, ...]) -> Decision | None:
    markers = _player_ad_controls(controls)
    for label in _SKIP_LABELS:
        if skip := _target(markers, {"AXButton"}, label):
            return _point(snap, skip, "പരസ്യം ഒഴിവാക്കാൻ {label} അമർത്തൂ.", "Use {label} to skip the ad.")
    if markers:
        return _decision(snap, "clarify", "പരസ്യം ഏതാനും സെക്കൻഡിനുള്ളിൽ തീരും.",
                         "The ad will finish in a few seconds.")
    return None


def _player_ad_controls(controls: tuple[Control, ...]) -> tuple[Control, ...]:
    player = tuple(c for c in controls if _key(c) in _PLAYER)
    if not player:
        return ()  # Home and search results can both contain display ads.
    seek = _target(controls, {"AXSlider"}, "seek slider")
    anchors = (seek,) if seek is not None else player
    left = min(c.frame[0] for c in anchors)
    right = max(c.frame[0] + c.frame[2] for c in anchors)
    bottom = max(c.frame[1] + c.frame[3] for c in anchors)
    side_margin = 24 if seek is not None else 64
    # Ad overlays sit above the playback bar, near its edges, or just below it.
    return tuple(c for c in controls if c.frame[0] < right + side_margin
                 and c.frame[0] + c.frame[2] > left - side_margin
                 and c.frame[1] < bottom + 64 and _ad_marker(c) is not None)


@dataclass
class YouTubeGuide:
    intent: Intent
    search_phase: str = "start"
    prior_results: tuple[tuple[str, str], ...] = ()
    result_label: str | None = None
    replacing_search: bool = False
    had_player: bool = False
    last_key: tuple[str, str] | None = None
    retry_at: float | None = None
    settings_retry_used: bool = False

    def decide(self, snap: Snapshot) -> Decision:
        controls = tuple(sorted(snap.controls, key=_rank))
        deadline, self.retry_at = self.retry_at, None
        if ad := _ad(snap, controls):
            return ad
        if self.intent.action == "exit_fullscreen":
            return _decision(snap, "clarify", "ഫുൾ സ്ക്രീനിൽ നിന്ന് പുറത്തുവരാൻ Esc അമർത്തൂ.",
                             "Press Esc to leave full screen.")
        if self.intent.action == "find":
            decision = self._find(snap, controls)
        elif self.intent.action == "speed":
            decision = self._speed(snap, controls, deadline)
        elif self.intent.action == "captions":
            decision = self._captions(snap, controls, deadline)
        else:
            decision = self._player(snap, controls)
        if decision.control_id is not None and (target := snap.control(decision.control_id)) is not None:
            self.last_key = _key(target)
        return decision

    def _settings(self, snap: Snapshot, controls: tuple[Control, ...], deadline: float | None) -> Decision:
        gear = _target(controls, {"AXPopUpButton", "AXButton"}, "settings")
        if not any(_setting_name(c) for c in controls):
            if gear is None:
                return _await_player(snap, controls)
            if self.settings_retry_used and self.last_key == _key(gear):
                return self._reopen_settings(snap, gear)
            return _point(snap, gear, "{label} അമർത്തൂ.", "Open {label}.")
        if self.settings_retry_used:
            return _decision(snap, "clarify", "ആ ഓപ്ഷൻ ഇപ്പോഴും സെറ്റിങ്‌സിൽ കാണുന്നില്ല.",
                             "That option still isn’t visible in Settings.")
        if gear is not None:
            now = monotonic()
            if deadline is not None and now >= deadline:
                self.settings_retry_used = True
                return self._reopen_settings(snap, gear)
            self.retry_at = deadline if deadline is not None else now + _SETTINGS_RETRY_S
        return _decision(snap, "clarify", "സെറ്റിങ്‌സ് പട്ടിക തുറക്കുന്നതുവരെ ഒന്ന് കാത്തിരിക്കൂ.",
                         "Wait for the Settings menu to finish opening.")

    @staticmethod
    def _reopen_settings(snap: Snapshot, gear: Control) -> Decision:
        return _point(snap, gear, "{label} അമർത്തി അടച്ചിട്ട് വീണ്ടും തുറക്കൂ.",
                      "Close {label}, then open it again.")

    def _find(self, snap: Snapshot, controls: tuple[Control, ...]) -> Decision:
        search = _target(controls, _SEARCH, "search")
        submit = _target(controls, {"AXButton"}, "search")
        links = _result_links(controls)
        fingerprint = tuple((c.role, _video_key(c)) for c in links)
        result = _best_result(links, self.intent.titles)
        if result is not None and snap.below_fold_count > 0 and _COLLECTION.search(_phrase(result.label)):
            result = None
        play = _target(controls, {"AXButton"}, "play")
        pause = _target(controls, {"AXButton"}, "pause")
        player_visible = _has_player(controls)
        results_ui = any(
            c.role in {"AXButton", "AXHeading", "AXPopUpButton"}
            and _phrase(c.label) in {"filters", "search filters", "search results"}
            for c in controls
        )
        if self.search_phase == "watch":
            on_watch = player_visible and (
                not self.had_player or fingerprint != self.prior_results
            )
            if on_watch and pause is not None:
                return _decision(snap, "complete", "വീഡിയോ ഇപ്പോൾ പ്ലേ ചെയ്യുന്നു.", "The video is playing.")
            if on_watch and play is not None:
                return _point(snap, play, "വീഡിയോ തുടങ്ങാൻ {label} അമർത്തൂ.", "Use {label} to start the video.")
            if on_watch:
                return _await_player(snap, controls)
            if result is not None and _phrase(result.label) == self.result_label:
                return _point(snap, result, "വീഡിയോ കാണാൻ {label} അമർത്തൂ.", "Open {label} to play the video.")
        elif self.search_phase == "start":
            if not player_visible and (results_ui or (links and search and search.filled is True)):
                self.search_phase = "results"
            elif search is not None:
                self.search_phase, self.prior_results = "typing", fingerprint
                self.replacing_search = search.filled is True
        if self.search_phase == "typing" and search is not None:
            if fingerprint != self.prior_results and links and not player_visible:
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
            self.had_player = player_visible
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
            title = _search_query(self.intent.titles[0])
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
        return _await_player(snap, controls)

    def _speed(self, snap: Snapshot, controls: tuple[Control, ...], deadline: float | None) -> Decision:
        requested = self.intent.speed
        assert requested is not None  # parse_intent supplies a speed for every speed intent.
        speed = _menu(controls, "Playback speed")
        slider = next((value for c in controls if c.role == "AXSlider"
                       and (value := _SPEED_SLIDER.fullmatch(_phrase(c.label)))), None)
        row_value = _SPEED_VALUE.fullmatch(_phrase(speed.label)) if speed is not None else None
        value = slider or row_value
        current = Decimal(value[1]) if value is not None else None
        if current is None and speed is not None and _phrase(speed.label) == "playback speed normal":
            current = Decimal(1)
        if current is not None and abs(current - requested) <= _SPEED_TOLERANCE:
            return _speed_complete(snap, requested)
        rates = [(Decimal(value[1]), c) for c in controls if c.role in _MENU and c.enabled
                 and (value := _SPEED_PRESET.fullmatch(_phrase(c.label)))]
        if target := next((c for rate, c in rates if rate == requested), None):
            if current is None and target.filled is True:
                return _speed_complete(snap, requested)
            return _point(snap, target, "വേഗം മാറ്റാൻ {label} അമർത്തൂ.", "Choose {label} for that playback speed.")
        decrease = _target(controls, {"AXButton"}, "decrease playback speed 0.05")
        increase = _target(controls, {"AXButton"}, "increase playback speed 0.05")
        decrease = decrease or _target(controls, {"AXButton"}, "decrease playback speed")
        increase = increase or _target(controls, {"AXButton"}, "increase playback speed")
        if rates or slider is not None or decrease is not None or increase is not None:
            return _adjust_speed(snap, requested, current, decrease, increase)
        if speed is not None:
            return _point(snap, speed, "വീഡിയോയുടെ വേഗം മാറ്റാൻ {label} തുറക്കൂ.",
                          "Open {label} to see the available speeds.")
        if self.last_key is not None and _SPEED_PRESET.fullmatch(self.last_key[1]):
            return _decision(snap, "clarify", "വേഗം മാറിയോ എന്ന് വീഡിയോ നോക്കി ഉറപ്പാക്കൂ.",
                             "Check that the video is playing at the speed you chose.")
        return self._settings(snap, controls, deadline)

    def _captions(self, snap: Snapshot, controls: tuple[Control, ...], deadline: float | None) -> Decision:
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
        caption_menu = _menu(controls, "Subtitles/CC")
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
        if cc is not None and cc.enabled and cc.filled is False and not any(_setting_name(c) for c in controls):
            return _point(snap, cc, "സബ്‌ടൈറ്റിൽ ഓണാക്കാൻ {label} അമർത്തൂ.", "Click {label} to turn on captions.")
        return self._settings(snap, controls, deadline)


class YouTubePrivacy(PrivacyProfile):
    def filter_snapshot(self, snap: Snapshot) -> Snapshot:
        player_ads = {c.id for c in _player_ad_controls(snap.controls)}
        controls = []
        for control in snap.controls:
            if (name := _setting_name(control)) in _SHARED_SETTINGS:
                control = replace(control, label=name, identifier=None, group=None)
            elif (marker := _ad_marker(control)) is not None:
                if control.id not in player_ads:
                    continue
                if _key(control) not in _AD_SKIP_BUTTONS:
                    # Share the marker as context, without allowing a pointer to an ad or advertiser.
                    control = replace(control, role="AXStaticText", label=marker, identifier=None, group=None)
            controls.append(control)
        return super().filter_snapshot(replace(snap, controls=tuple(controls)))


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
    privacy=YouTubePrivacy(frozenset((role, _phrase(label)) for role, label in (
        *_PLAYER, *_PLAYER_SHORTCUT_LABELS, *_AD_SKIP_BUTTONS,
        *(("AXStaticText", label) for label in _AD_MARKERS),
        *((role, "Search") for role in {*_SEARCH, "AXButton"}),
        *((role, label) for role in _SETTINGS_ROLES for label in _SHARED_SETTINGS),
        *((role, "Malayalam") for role in _MENU),
    ))),
    practice_result="",
)
