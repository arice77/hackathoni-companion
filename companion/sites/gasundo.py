"""Read-only, Malayalam-first guidance for the GasUndo restaurant catalog."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..contracts import Control, Decision, DecisionKind, Snapshot
from ..voice import sarvam
from . import PrivacyProfile, SitePack, SiteStep, _phrase

HOSTS = frozenset({"gasundo.live", "www.gasundo.live"})
DISTRICT_IDS = frozenset({"district-select-hero", "district-select-compact"})
SEARCH_IDS = frozenset({"restaurant-search-panel", "restaurant-search-mobile"})
DISTRICTS = (
    "Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam",
    "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad",
)
_DISTRICT_ML = (
    "ആലപ്പുഴ", "എറണാകുളം", "ഇടുക്കി", "കണ്ണൂർ", "കാസർഗോഡ്", "കൊല്ലം", "കോട്ടയം",
    "കോഴിക്കോട്", "മലപ്പുറം", "പാലക്കാട്", "പത്തനംതിട്ട", "തിരുവനന്തപുരം", "തൃശ്ശൂർ", "വയനാട്",
)
DISTRICT_NAMES = {name.casefold(): name for name in DISTRICTS}
_DISTRICT_ALIASES = {**DISTRICT_NAMES, **dict(zip(_DISTRICT_ML, DISTRICTS, strict=True)),
                     "kochi": "Ernakulam", "കൊച്ചി": "Ernakulam", "alleppey": "Alappuzha",
                     "എറണാകുളത്ത്": "Ernakulam", "കൊച്ചിയിൽ": "Ernakulam", "ആലപ്പുഴയിൽ": "Alappuzha"}
SUGGESTION_PREFIX = "gasundo-suggestion:"
STATUS_TEXT = {
    "Open now": ("തുറന്നിരുന്നു", "open"),
    "Limited menu": ("മെനുവിൽ കുറച്ച് വിഭവങ്ങൾ മാത്രമേ ഉണ്ടായിരുന്നുള്ളൂ", "limited menu"),
    "Closed for gas shortage": ("ഗ്യാസ് ക്ഷാമം കാരണം അടച്ചിരുന്നു", "closed because of the gas shortage"),
}
STATUS_NOTES = frozenset((*STATUS_TEXT, "Needs a fresh update", "No recent report", "Freshness", "Stale",
                          "recently", "just now"))
REPORT_AGE = re.compile(r"[0-9]{1,5}(?: min|h|d) ago")
CATALOG_ERROR = re.compile(r"Could not load the (?:\w+ )?restaurant catalog right now\.?", re.IGNORECASE)
SEARCH = SiteStep("AXTextField", "Search restaurants", "‘Search restaurants’ എന്ന ബോക്സ് ഉപയോഗിക്കൂ.",
                  "Use the ‘Search restaurants’ box.")
_MALAYALAM = re.compile(r"[\u0d00-\u0d7f]")
_OFFLINE_NAMES = ((re.compile(r"ബെ[ക്‌]*താ[ഷ്ശ]+്?\s*കാക്കനാ[ട്ട്]+"), "Bektash Kakkanad"),)
_VAGUE_NAMES = {"it", "the restaurant", "this restaurant", "that restaurant", "the hotel", "this place"}
_FIND = (
    re.compile(r"is (?P<name>.+?) (?:open|closed)(?: now| today)?(?: in .+)?(?: or not)?"),
    re.compile(r"(?:check|see|i want to know|tell me) (?:if|whether) (?P<name>.+?) is (?:open|closed)"
               r"(?: now| today)?(?: in .+)?"),
    re.compile(r"(?:find|check the status of|look up) (?P<name>.+)"),
    re.compile(r"(?P<name>.+?) (?:open aano|thurannittundo|open ആണോ|തുറന്നിട്ടുണ്ടോ|അടച്ചിട്ടുണ്ടോ)"
               r"(?: എന്ന് (?:അറിയണം|നോക്കണം|അറിയാൻ ആഗ്രഹിക്കുന്നു)| എന്നറിയണം| ennu (?:ariyanam|nokkanam))?"),
    re.compile(r"(?P<name>.+?)(?:ിന്റെ|ൻ്റെ)? (?:നില|സ്റ്റാറ്റസ്|status) (?:എങ്ങനെ നോക്കാം|എന്താണ്|engane nokkam)"),
)
_OPEN = re.compile(r"which (?:hotels|restaurants) are open|open (?:restaurants|filter)|തുറന്നിരിക്കുന്ന|തുറന്ന ഹോട്ടലുകൾ")
_FRESHNESS = re.compile(r"when was (?:this|the) .*updated|how old is (?:this|the) report|എപ്പോഴാണ് പുതുക്കിയത്")


def _normalized_name(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", _phrase(text)).split())


def _district(text: str) -> str | None:
    for alias, district in _DISTRICT_ALIASES.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
            return district
    return None


@dataclass(frozen=True)
class Intent:
    name: str = ""
    district: str | None = None
    action: str = "unsupported"


def _find_name(text: str) -> str:
    for pattern in _FIND:
        if match := pattern.fullmatch(text):
            name = match["name"].strip(" '‘’\"“”")
            for alias in _DISTRICT_ALIASES:
                name = re.sub(rf" in {re.escape(alias)}$", "", name).strip()
            return name
    return ""


def _latin_name(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    return (0 < len(text) <= 120 and bool(letters) and _phrase(text) not in _VAGUE_NAMES
            and all("LATIN" in unicodedata.name(char, "") for char in letters)
            and all(char.isalnum() or char in " .,&'’()-" for char in text))


def _romanize(name: str) -> str:
    if len(name) <= 120:
        try:
            text = " ".join(sarvam.transliterate_text(name, "ml-IN", "en-IN").split())
        except sarvam.SarvamError:
            text = ""
        if _latin_name(text):
            return text
    return next((latin for alias, latin in _OFFLINE_NAMES if alias.fullmatch(name)), "")


def _intent(question: str) -> Intent:
    parts = [_phrase(part) for part in question.split(" / ", 1)]
    district = next((found for part in parts if (found := _district(part))), None)
    if any(_FRESHNESS.search(part) for part in parts):
        return Intent(district=district, action="card")
    if any(_OPEN.search(part) for part in parts):
        return Intent(district=district, action="open")
    names = [_find_name(part) for part in parts]
    name = next((candidate for candidate in reversed(names) if _latin_name(candidate)), "")
    if not name and (native := next((candidate for candidate in names if _MALAYALAM.search(candidate)), "")):
        name = _romanize(native)
        if not name:
            return Intent(district=district, action="spelling")
    if _normalized_name(name) == "bektash kakkanad":
        return Intent("Bektash Kakkanad", district or "Ernakulam", "find")
    return Intent(name, district, "find") if name else Intent()


def _decision(snap: Snapshot, kind: DecisionKind, ml: str, en: str, control: Control | None = None) -> Decision:
    return Decision(kind, snap.snapshot_id, ml, en, control.id if control else None, "sarvam")


def _only(controls) -> Control | None:
    matches = list(controls)
    return matches[0] if len(matches) == 1 else None


def _report(snap: Snapshot, anchor: Control, name: str) -> Decision:
    x, y, _, height = anchor.frame
    notes = {
        control.label for control in snap.controls
        if control.role == "AXStaticText" and abs(control.frame[0] - x) <= 460
        and y - 10 <= control.frame[1] <= y + height + 310
    }
    ages = sorted(note for note in notes if REPORT_AGE.fullmatch(note) or note == "just now")
    age = ages[0] if len(ages) == 1 else ""
    status = next((label for label in STATUS_TEXT if label in notes), None)
    if "No recent report" in notes or "Needs a fresh update" in notes:
        return _decision(snap, "complete", f"‘{name}’ എന്ന സ്ഥലത്തിന് പുതിയ റിപ്പോർട്ട് കാണുന്നില്ല. ഇപ്പോഴത്തെ നില അറിയില്ല.",
                         f"GasUndo shows no recent report for ‘{name}’. Its current status is unknown.")
    if status:
        ml, en = STATUS_TEXT[status]
        stale = "Stale" in notes or bool(age and age.endswith("d ago"))
        ml_tail, en_tail = _age_text(age)
        if stale:
            ml_tail += " റിപ്പോർട്ട് പഴയതാണ്. ഇപ്പോഴത്തെ നില അറിയില്ല."
            en_tail += " The report is stale. Its current status is unknown."
        return _decision(snap, "complete", f"‘{name}’ എന്ന സ്ഥലത്തെക്കുറിച്ചുള്ള റിപ്പോർട്ട് പ്രകാരം {ml}. {ml_tail}",
                         f"GasUndo’s report for ‘{name}’ says {en}. {en_tail}")
    return _decision(snap, "clarify", "ഈ ഹോട്ടലിന്റെ റിപ്പോർട്ട് കാണാൻ അതിന്റെ വിവരങ്ങളിൽ കുറച്ച് താഴേക്ക് നീങ്ങൂ.",
                     "Scroll down in the restaurant details to see the report.")


def _age_text(age: str) -> tuple[str, str]:
    if age == "just now":
        return "ഇപ്പോൾ പുതുക്കിയതായാണ് കാണിക്കുന്നത്.", "It shows the report was updated just now."
    if match := re.fullmatch(r"([0-9]+)( min|h|d) ago", age):
        count = int(match[1])
        ml_unit, en_unit = {" min": ("മിനിറ്റ്", "minute"), "h": ("മണിക്കൂർ", "hour"),
                            "d": ("ദിവസം", "day")}[match[2]]
        plural = "" if count == 1 else "s"
        return (f"{count} {ml_unit} മുമ്പ് പുതുക്കിയതായാണ് കാണിക്കുന്നത്.",
                f"It shows the report was updated {count} {en_unit}{plural} ago.")
    return "പുതുക്കിയ സമയം വ്യക്തമല്ല.", "The update time is unclear."


class GasUndoPack(SitePack):
    def is_practice(self, snap: Snapshot) -> bool:
        return False

    def start_guidance(self, question: str) -> GasUndoGuide:
        return GasUndoGuide(_intent(question))


PACK = GasUndoPack("GasUndo", HOSTS, "", (), SEARCH, (), PrivacyProfile(frozenset()), "")


@dataclass
class GasUndoGuide:
    intent: Intent

    def decide(self, snap: Snapshot) -> Decision:
        if not PACK.matches(snap) or self.intent.action == "unsupported":
            return _decision(snap, "unsupported",
                             "GasUndo-ൽ ഒരു ഹോട്ടൽ കണ്ടെത്താനോ അതിന്റെ റിപ്പോർട്ട് വായിക്കാനോ സഹായിക്കാം.",
                             "I can help find a restaurant or read its report on GasUndo.")
        if self.intent.action == "spelling":
            return _decision(snap, "clarify",
                             "ഹോട്ടലിന്റെ പേര് ഇംഗ്ലീഷ് അക്ഷരത്തിൽ പറഞ്ഞോ എഴുതിയോ വീണ്ടും ചോദിക്കൂ.",
                             "Ask again with the restaurant’s name in English letters.")
        district = _only(c for c in snap.controls if c.enabled and c.role == "AXPopUpButton"
                         and c.label.startswith("Select district"))
        if self.intent.district and district and district.label != f"Select district: {self.intent.district}":
            name = self.intent.district
            return _decision(snap, "point", f"‘Select district’ തുറന്ന് ‘{name}’ തിരഞ്ഞെടുക്കൂ.",
                             f"Open ‘Select district’ and choose ‘{name}’.", district)
        if any(c.role == "AXStaticText" and CATALOG_ERROR.fullmatch(c.label) for c in snap.controls):
            return _decision(snap, "clarify", "ഈ ജില്ലയിലെ പട്ടിക ഇപ്പോൾ തുറക്കുന്നില്ല. മറ്റൊരു ജില്ല തിരഞ്ഞെടുത്ത് നോക്കൂ.",
                             "GasUndo couldn’t load this district’s catalog. Try selecting another district.")
        name = _normalized_name(self.intent.name)
        card = _only(c for c in snap.controls if c.role == "AXButton" and c.label.startswith("Copy ")
                     and c.label.endswith(" link") and (not name or _normalized_name(c.label[5:-5]) == name))
        if card and self.intent.action in {"card", "find"}:
            return _report(snap, card, card.label[5:-5])
        if name and self.intent.action == "find":
            heading = _only(c for c in snap.controls if c.role == "AXHeading" and _normalized_name(c.label) == name)
            if heading:
                return _report(snap, heading, heading.label)
        if self.intent.action == "card":
            return _decision(snap, "clarify", "‘Search restaurants’ വഴി ഒരു ഹോട്ടൽ തിരഞ്ഞെടുത്തിട്ട് വീണ്ടും ചോദിക്കൂ.",
                             "Choose a restaurant through ‘Search restaurants’, then ask again.")
        if self.intent.action == "open":
            opened = _only(c for c in snap.controls if c.enabled and c.role == "AXButton"
                           and re.fullmatch(r"Open(?:\s*[0-9,]+)?", c.label, re.IGNORECASE))
            if opened:
                return _decision(snap, "point",
                                 "മാപ്പിൽ തുറന്നതായി റിപ്പോർട്ട് ചെയ്ത ഇടങ്ങൾ കാണാൻ ‘Open’ അമർത്തൂ. "
                                 "ഒരു ഹോട്ടലിന്റെ പുതിയ വിവരം നോക്കാൻ ‘Search restaurants’ ഉപയോഗിക്കൂ.",
                                 "‘Open’ filters the map to places reported open. Use ‘Search restaurants’ to check a specific report.",
                                 opened)
        search = _only(c for c in snap.controls if c.enabled and c.role in {"AXTextField", "AXSearchField"}
                       and c.label == SEARCH.label)
        if search:
            if name and search.filled:
                results = [c for c in snap.controls if c.enabled and c.role == "AXButton"
                           and (c.identifier or "").startswith(SUGGESTION_PREFIX)]
                exact = _only(c for c in results if _normalized_name(c.label) == name)
                result = exact or _only(c for c in results if _normalized_name(c.label).startswith(f"{name} "))
                if result:
                    return _decision(snap, "point", f"റിപ്പോർട്ട് കാണാൻ ‘{result.label}’ അമർത്തൂ.",
                                     f"Choose ‘{result.label}’ to see its report.", result)
            if name:
                display = self.intent.name
                return _decision(snap, "point",
                                 f"‘Search restaurants’ എന്ന ബോക്സിൽ ‘{display}’ ടൈപ്പ് ചെയ്യൂ. താഴെ പേരുകൾ വരും.",
                                 f"Type ‘{display}’ into ‘Search restaurants’. The suggestions appear below it.", search)
            return SEARCH.point(snap, search)
        return _decision(snap, "clarify", "ഈ പേജിൽ ‘Search restaurants’ കാണുന്ന ഭാഗത്തേക്ക് നീങ്ങൂ.",
                         "Scroll until ‘Search restaurants’ is visible.")
