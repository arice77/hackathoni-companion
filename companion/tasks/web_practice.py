"""Script for the generic business form. Malayalam is a draft for native-speaker review."""

import re

from . import Screen, Step, Task

TASK = Task(
    name="web_practice",
    bundle_id="com.apple.Safari",
    intent=re.compile(
        r"\b(?:form|(?:business|practice) details|fill (?:in|out)|application|apeksha|poorippikk\w*|nirakk\w*)\b|"
        r"ഫോം|ഫോറം|പൂരിപ്പി|അപേക്ഷ",
        re.IGNORECASE,
    ),
    screens=(
        Screen("Business Details", (
            Step("business-name", "‘Business Name’ എന്ന ബോക്സിൽ പരിശീലനത്തിനായി ഒരു സാങ്കൽപ്പിക കടപ്പേര് എഴുതുക.",
                 "In ‘Business Name’, type a made-up shop name for practice."),
            Step("district", "‘District’ ലിസ്റ്റിൽ കട സ്ഥിതി ചെയ്യുന്ന ജില്ല തിരഞ്ഞെടുക്കുക. പരിശീലനത്തിന് ഏതെങ്കിലും ജില്ല മതി.",
                 "‘District’ is where the shop is based. Choose any district for practice."),
            Step("category", "‘Category’ ലിസ്റ്റിൽ കടയിൽ ചെയ്യുന്ന ജോലിയുടെ തരം തിരഞ്ഞെടുക്കുക.",
                 "Under ‘Category’, choose the type of work the shop does."),
        ), Step("details-next", "രേഖകൾ ചേർക്കുന്ന പേജിലെത്താൻ ‘Next’ അമർത്തുക.",
                "Click ‘Next’ to go to the documents step.")),
        Screen("Documents", (
            Step("attach-sample", "‘Attach Sample Document’ അമർത്തുക. ഒരു മാതൃക മാത്രമാണ് ചേർക്കുന്നത്; സ്വന്തം ഫയൽ വേണ്ട.",
                 "Click ‘Attach Sample Document’. This adds a sample; you don't need a file of your own.",
                 done_note="document-note", done_prefix="Sample attached"),
        ), Step("documents-next", "അവസാന പരിശോധനയിലേക്ക് പോകാൻ ‘Next’ അമർത്തുക.",
                "Click ‘Next’ to review before saving.")),
        Screen("Review", (
            Step("declaration", "നൽകിയ വിവരങ്ങൾ സാങ്കൽപ്പികമാണെങ്കിൽ ‘I used only synthetic data’ ടിക്ക് ചെയ്യുക.",
                 "Tick ‘I used only synthetic data’ if you used only made-up details."),
        ), Step("save", "‘Save’ അമർത്തുക. പരിശീലനം പൂർത്തിയായതിന്റെ രേഖ ഈ കമ്പ്യൂട്ടറിൽ മാത്രം സൂക്ഷിക്കും.",
                "Click ‘Save’ to keep a practice receipt on this computer only.")),
    ),
    complete_status_prefix="Training complete",
    complete_ml="പരിശീലനം പൂർത്തിയായി. വിവരങ്ങളൊന്നും പുറത്തേക്ക് അയച്ചിട്ടില്ല.",
    complete_en="Practice complete. No details were sent outside this computer.",
    receipt_file="web-practice-complete.json",
    unsupported_ml="ഇപ്പോൾ ഈ ബിസിനസ് പരിശീലന ഫോം പൂരിപ്പിക്കാൻ മാത്രമേ സഹായിക്കാനാവൂ.",
    unsupported_en="Right now I can only help fill out this business practice form.",
)
