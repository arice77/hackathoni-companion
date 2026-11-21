"""Unscripted guidance for the selected Safari page. No fixture writes a receipt."""

import re

from . import Task

TASK = Task(
    name="web_any",
    bundle_id="com.apple.Safari",
    intent=re.compile(r"\S"),
    screens=(),
    complete_status_prefix="\x00",
    complete_ml="",
    complete_en="",
    receipt_file="web-any-receipt.json",
)
