"""AIMS Crop Insurance Compensation training form (prototype, kept for reference).

Labels follow the AIMS manual pages cited in apps/aims-training/TrainingForm.swift.
Malayalam wording is a first draft and needs a native speaker's check.
"""

import re

from . import Screen, Step, Task

# Screens and labels follow the AIMS manual pages cited in apps/aims-training/TrainingForm.swift.
# (screen title, ordered steps, instruction for the screen's final button or None if the
#  screen finishes with a status message instead)
_SCREENS = [
    ("Application Submission", [
        Step("classification", "‘Classification’ ലിസ്റ്റിൽ ‘Insurance & Calamity Relief Services’ തിരഞ്ഞെടുക്കുക",
             "Under ‘Classification’, choose ‘Insurance & Calamity Relief Services’"),
        Step("service", "‘Service’ ലിസ്റ്റിൽ ‘Crop Insurance Compensation’ തിരഞ്ഞെടുക്കുക",
             "Under ‘Service’, choose ‘Crop Insurance Compensation’"),
    ], Step("next", "ഇനി ‘Apply for New’ അമർത്തുക", "Now click ‘Apply for New’")),
    ("Calamity Details", [
        Step("calamity-date", "‘Calamity Date’ ലിസ്റ്റിൽ കൃഷിഭവൻ രേഖപ്പെടുത്തിയ തീയതി തിരഞ്ഞെടുക്കുക",
             "Choose the date your Krishi Bhavan recorded under ‘Calamity Date’"),
        Step("calamity-type", "‘Calamity Type’ ലിസ്റ്റിൽ ‘Flood’ തിരഞ്ഞെടുക്കുക",
             "Choose ‘Flood’ under ‘Calamity Type’"),
        Step("calamity-description", "‘Calamity Description’ ബോക്സിൽ എന്താണ് സംഭവിച്ചതെന്ന് ചുരുക്കി എഴുതുക",
             "Briefly describe what happened in ‘Calamity Description’"),
    ], Step("next", "‘Save »’ അമർത്തുക", "Click ‘Save »’")),
    ("Crop Information", [
        Step("insured-crop", "‘My Insured Crops’ ലിസ്റ്റിൽ ഇൻഷുർ ചെയ്ത നെല്ല് തിരഞ്ഞെടുക്കുക",
             "Choose your insured paddy under ‘My Insured Crops’"),
        Step("crop-stage", "‘Crop Stages’ ലിസ്റ്റിൽ ‘Mainfield’ തിരഞ്ഞെടുക്കുക", "Choose ‘Mainfield’ under ‘Crop Stages’"),
        Step("quantity-applied", "‘Quantity Applied’ ബോക്സിൽ നഷ്ടപ്പെട്ട അളവ് (സെന്റ്) നൽകുക",
             "Enter the damaged quantity (in cents) in ‘Quantity Applied’"),
        Step("crop-image", "‘Upload Crop Image’ എന്നതിലെ ‘Browse...’ അമർത്തി ഫോട്ടോ ചേർക്കുക (1.91 MB വരെ)",
             "Click ‘Browse...’ under ‘Upload Crop Image’ to add the photo (max 1.91 MB)",
             done_note="crop-image-file", done_prefix="Chosen"),
        Step("add-crop", "‘+Add’ അമർത്തുക — വിള ‘Added Details’ പട്ടികയിൽ വരും",
             "Click ‘+Add’ so the crop appears under ‘Added Details’",
             done_note="added-details", done_prefix="Added Details: 1"),
    ], Step("next", "‘Submit Application’ അമർത്തുക. ഇത് പരിശീലനമാണ്, ഒന്നും അയയ്ക്കില്ല.",
            "Click ‘Submit Application’. This is training; nothing is sent.")),
    ("Application View", [
        Step("declaration", "വിവരങ്ങൾ വായിച്ച് ശരിയാണെങ്കിൽ സത്യപ്രസ്താവന ബോക്സ് ടിക്ക് ചെയ്യുക",
             "Read the details and tick the declaration if they are correct"),
    ], None),
]

INTENT = re.compile(
    r"crop|loss|paddy|flood|claim|compensat|damage|apply|application|form|report|next|help|"
    r"നഷ്ട|നെല്ല്|കൃഷി|അപേക്ഷ|വെള്ളപ്പൊക്ക|ഫോം|nasht|krishi|nellu|apeksha",
    re.IGNORECASE,
)




TASK = Task(
    name="aims",
    bundle_id="in.hackathoni.crop-loss-training",
    intent=INTENT,
    screens=tuple(Screen(title, tuple(steps), final) for title, steps, final in _SCREENS),
    complete_status_prefix="Training draft complete",
    complete_ml="പരിശീലന അപേക്ഷ പൂർത്തിയായി. ഒന്നും സമർപ്പിച്ചിട്ടില്ല — യഥാർത്ഥ അപേക്ഷ AIMS-ൽ നൽകണം.",
    complete_en="Training application complete. Nothing was submitted — the real one is filed on AIMS.",
    receipt_file="training-declaration_ticked.json",
    unsupported_ml="ഇപ്പോൾ വിളനഷ്ട അപേക്ഷയുടെ പരിശീലന ഫോം മാത്രമേ കാണിച്ചുതരാൻ കഴിയൂ.",
    unsupported_en="Right now I can only guide the crop-loss training form.",
)
