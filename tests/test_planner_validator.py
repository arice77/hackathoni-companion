import time
import unittest

from companion.contracts import Control, Decision, Snapshot
from companion.planner import ScriptedPlanner
from companion.validator import validate

WIN = (400.0, 130.0, 620.0, 520.0)


def snap(title, controls, sid="s1", age=0.0):
    base = [Control("c00", "AXStaticText", title, (448, 193, 322, 26), identifier="screen-title"),
            Control("c99", "AXStaticText", "", (448, 647, 574, 18), identifier="status")]
    return Snapshot(sid, time.time() - age, "in.hackathoni.crop-loss-training", 1, "w", WIN,
                    tuple(base + controls))


def field(cid, ident, filled, role="AXTextField", label=None, frame=(680, 235, 222, 26), enabled=True):
    return Control(cid, role, label or ident, frame, enabled, ident, filled)


SCREEN1 = "Step 1 of 3 · Farmer & Land Details"
ASK = "how do I report paddy loss"


class PlannerTests(unittest.TestCase):
    p = ScriptedPlanner()

    def test_first_unfilled_field(self):
        s = snap(SCREEN1, [field("c01", "farmer-id", True), field("c02", "panchayat", False, "AXPopUpButton"),
                           field("c03", "krishi-bhavan", False, "AXPopUpButton"), field("c04", "survey-no", False),
                           field("c05", "land-area", False), field("c06", "next", None, "AXButton")])
        d = self.p.decide(ASK, s)
        self.assertEqual((d.kind, d.control_id), ("point", "c02"))

    def test_all_filled_points_at_next(self):
        ids = ["farmer-id", "panchayat", "krishi-bhavan", "survey-no", "land-area"]
        s = snap(SCREEN1, [field(f"c{i}", x, True) for i, x in enumerate(ids, 1)] + [field("c9", "next", None, "AXButton")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c9")

    def test_similar_labels_use_identifier_not_label(self):
        # Two fields both labelled "Area"; the planner must pick by identifier/order.
        s = snap("Step 2 of 3 · Crop Loss Details", [
            field("c1", "crop", True, "AXPopUpButton"), field("c2", "season", True, "AXPopUpButton"),
            field("c3", "cause", True, "AXPopUpButton"),
            field("c4", "land-area", False, label="Area"), field("c5", "affected-area", False, label="Area"),
            field("c6", "next", None, "AXButton")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c5")

    def test_missing_control_is_unsupported(self):
        s = snap(SCREEN1, [field("c01", "farmer-id", True)])
        self.assertEqual(self.p.decide(ASK, s).kind, "unsupported")

    def test_empty_question_clarifies(self):
        self.assertEqual(self.p.decide("  ", snap(SCREEN1, [])).kind, "clarify")

    def test_off_topic_question_unsupported(self):
        self.assertEqual(self.p.decide("what's the weather", snap(SCREEN1, [])).kind, "unsupported")

    def test_malayalam_question_accepted(self):
        s = snap(SCREEN1, [field("c01", "farmer-id", False)])
        self.assertEqual(self.p.decide("നെല്ല് നഷ്ടം അപേക്ഷ", s).kind, "point")

    def test_unknown_screen(self):
        self.assertEqual(self.p.decide(ASK, snap("Login", [])).kind, "unsupported")

    def test_attachment_done_detected_from_note(self):
        s = snap("Step 3 of 3 · Evidence & Review", [
            field("c1", "photo", None, "AXButton"),
            Control("c2", "AXStaticText", "Attached: sample-paddy-field.jpg (synthetic)", (0, 0, 1, 1), identifier="photo-file"),
            field("c3", "tax-receipt", None, "AXButton"),
            Control("c4", "AXStaticText", "No file attached", (0, 0, 1, 1), identifier="tax-receipt-file"),
            field("c5", "declaration", False, "AXCheckBox"), field("c6", "next", None, "AXButton")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c3")


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.s = snap(SCREEN1, [field("c01", "farmer-id", False),
                                field("c02", "off", False, frame=(2000, 2000, 10, 10)),
                                field("c03", "dis", False, enabled=False)])

    def test_ok(self):
        self.assertEqual(validate(Decision("point", "s1", "x", control_id="c01"), self.s), (True, "ok"))

    def test_invented_id_rejected(self):
        self.assertFalse(validate(Decision("point", "s1", "x", control_id="c77"), self.s)[0])

    def test_stale_snapshot_rejected(self):
        old = snap(SCREEN1, [field("c01", "farmer-id", False)], age=5)
        self.assertEqual(validate(Decision("point", "s1", "x", control_id="c01"), old)[1], "snapshot is stale")

    def test_other_snapshot_rejected(self):
        self.assertFalse(validate(Decision("point", "other", "x", control_id="c01"), self.s)[0])

    def test_offscreen_and_disabled_rejected(self):
        self.assertFalse(validate(Decision("point", "s1", "x", control_id="c02"), self.s)[0])
        self.assertFalse(validate(Decision("point", "s1", "x", control_id="c03"), self.s)[0])

    def test_point_without_id_rejected(self):
        self.assertFalse(validate(Decision("point", "s1", "x"), self.s)[0])


if __name__ == "__main__":
    unittest.main()
