"""Guide a supported site selected from the current Safari page's host."""

import re

from . import Task

TASK = Task(
    name="web_site",
    bundle_id="com.apple.Safari",
    intent=re.compile(r"\S"),
    screens=(),
    complete_status_prefix="\x00",
    complete_ml="",
    complete_en="",
    receipt_file="web-site-receipt.json",
)
