"""Quick Pay guidance based on the KSEB Safari Accessibility probe."""

from __future__ import annotations

import re

from . import PrivacyProfile, SiteGoal, SitePack, SiteStep, _phrase

QUICK_PAY = SiteStep(
    "AXLink", "Quick Pay",
    "ബിൽ കാണാൻ ‘Quick Pay’ അമർത്തൂ.",
    "Open ‘Quick Pay’ to see your electricity bill.",
    action=True,
)
CONSUMER = SiteStep(
    "AXTextField", "13 digit Consumer number",
    "നിങ്ങളുടെ കറന്റ് ബില്ലിലെ 13 അക്ക നമ്പർ ‘13 digit Consumer number’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ.",
    "Enter the 13-digit Consumer Number from your electricity bill in ‘13 digit Consumer number’.",
)
MOBILE = SiteStep(
    "AXTextField", "Enter Mobile Number",
    "കറന്റ് കണക്ഷനിൽ രജിസ്റ്റർ ചെയ്ത മൊബൈൽ നമ്പർ ‘Enter Mobile Number’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ.",
    "Enter the mobile number registered to your electricity connection in ‘Enter Mobile Number’.",
)
VERIFICATION = SiteStep(
    "AXTextField", "Enter text shown below",
    "ചിത്രത്തിലെ അക്ഷരങ്ങളും അക്കങ്ങളും നിങ്ങൾ തന്നെ വായിച്ച് ‘Enter text shown below’ എന്നിടത്ത് ടൈപ്പ് ചെയ്യൂ. "
    "വായിക്കാൻ പറ്റുന്നില്ലെങ്കിൽ ‘Refresh’ അമർത്തൂ.",
    "Read the image yourself and type what you see in ‘Enter text shown below’. "
    "If it’s hard to read, use ‘Refresh’ for a new image.",
)
REFRESH = SiteStep(
    "AXLink", "Refresh",
    "പുതിയ ചിത്രം കാണാൻ ‘Refresh’ അമർത്തൂ. എന്നിട്ട് ചിത്രത്തിലെ അക്ഷരങ്ങളും അക്കങ്ങളും നിങ്ങൾ തന്നെ വായിക്കൂ.",
    "Use ‘Refresh’ for a new image, then read its characters yourself.",
    action=True,
)
SEE_BILL = SiteStep(
    "AXButton", "Submit to see the bill",
    "വിവരങ്ങൾ ശരിയാണെന്ന് നോക്കിയ ശേഷം ബിൽ കാണാൻ ‘Submit to see the bill’ അമർത്തൂ.",
    "Check your entries, then use ‘Submit to see the bill’ to view the bill.",
    action=True,
)
_STEPS = (CONSUMER, MOBILE, VERIFICATION, SEE_BILL)
_PRACTICE_HEADING = "KSEB Quick Pay (practice)"
_PRACTICE_RESULT = "Bill Details (practice)"
_KNOWN_CONTROLS = (
    *((step.role, step.label) for step in (*_STEPS, QUICK_PAY, REFRESH)),
    ("AXHeading", "KSEB Quick Pay"), ("AXHeading", "Quick Pay"),
    ("AXHeading", "Consumer No"), ("AXHeading", "Registered Mobile Number"),
    ("AXHeading", "Enter the text in image"),
    ("AXHeading", _PRACTICE_HEADING), ("AXHeading", _PRACTICE_RESULT),
)

PACK = SitePack(
    name="KSEB Quick Pay",
    hosts=frozenset({"wss.kseb.in"}),
    practice_heading=_PRACTICE_HEADING,
    goals=(
        SiteGoal("refresh_image", (
            "I can't read the image", "I can’t read the image", "How do I refresh the captcha",
            "ചിത്രം വായിക്കാൻ പറ്റുന്നില്ല", "ക്യാപ്ച വായിക്കാൻ പറ്റുന്നില്ല", "Captcha vayikkan pattunnilla",
        ), REFRESH),
        SiteGoal("verification", (
            "Where do I type the verification text", "What does the image say", "Where do I enter the captcha",
            "ചിത്രത്തിലെ അക്ഷരങ്ങൾ എവിടെ എഴുതണം", "ക്യാപ്ച എവിടെ ടൈപ്പ് ചെയ്യണം", "Captcha evide type cheyyanam",
        ), VERIFICATION),
        SiteGoal("consumer_number", (
            "Where do I enter my consumer number", "Where do I type my consumer number",
            "Where can I find my consumer number", "Consumer number എവിടെ എഴുതണം",
            "കൺസ്യൂമർ നമ്പർ എവിടെ ടൈപ്പ് ചെയ്യണം", "Consumer number evide kodukkanam",
        ), CONSUMER),
        SiteGoal("registered_mobile", (
            "Which phone number should I enter", "Where do I enter my mobile number", "Which mobile number should I use",
            "ഏത് മൊബൈൽ നമ്പറാണ് കൊടുക്കേണ്ടത്", "രജിസ്റ്റർ ചെയ്ത നമ്പർ എവിടെ ടൈപ്പ് ചെയ്യണം",
            "Registered mobile number evide kodukkanam",
        ), MOBILE),
        SiteGoal("view_bill", (
            "How do I see my electricity bill", "I want to see my electricity bill", "I want to check my KSEB bill",
            "How do I open Quick Pay", "Open Quick Pay", "Can you help me see my KSEB bill",
            "എന്റെ കറന്റ് ബിൽ എങ്ങനെ കാണാം", "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം",
            "എനിക്ക് കറന്റ് ബിൽ കാണണം", "ക്വിക്ക് പേ എവിടെയാണ്",
            "Current bill engane nokkam", "KSEB bill engane kanam", "Quick Pay evideya",
        )),
    ),
    entry=QUICK_PAY,
    steps=_STEPS,
    privacy=PrivacyProfile(
        frozenset((role, _phrase(label)) for role, label in _KNOWN_CONTROLS),
        private_question=re.compile(r"(?<!\d)(?:\d[ .-]?){9,12}\d(?!\d)"),
    ),
    practice_result=_PRACTICE_RESULT,
)
