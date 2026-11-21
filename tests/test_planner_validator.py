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


SCREEN1 = "Application Submission"
ASK = "how do I claim crop insurance for paddy loss"


def note(cid, ident, text):
    return Control(cid, "AXStaticText", text, (0, 0, 1, 1), identifier=ident)


class PlannerTests(unittest.TestCase):
    p = ScriptedPlanner()

    def test_first_unfilled_field(self):
        s = snap(SCREEN1, [field("c01", "classification", True, "AXPopUpButton"),
                           field("c02", "service", False, "AXPopUpButton"), field("c06", "next", None, "AXButton")])
        d = self.p.decide(ASK, s)
        self.assertEqual((d.kind, d.control_id), ("point", "c02"))

    def test_all_filled_points_at_next(self):
        s = snap(SCREEN1, [field("c1", "classification", True, "AXPopUpButton"),
                           field("c2", "service", True, "AXPopUpButton"), field("c9", "next", None, "AXButton")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c9")

    def test_similar_labels_use_identifier_not_label(self):
        s = snap("Calamity Details", [
            field("c1", "calamity-date", True, "AXPopUpButton", label="Calamity"),
            field("c2", "calamity-type", False, "AXPopUpButton", label="Calamity"),
            field("c3", "calamity-description", False), field("c6", "next", None, "AXButton")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c2")

    def test_missing_control_is_unsupported(self):
        s = snap(SCREEN1, [field("c01", "classification", True, "AXPopUpButton")])
        self.assertEqual(self.p.decide(ASK, s).kind, "unsupported")

    def test_empty_question_clarifies(self):
        self.assertEqual(self.p.decide("  ", snap(SCREEN1, [])).kind, "clarify")

    def test_off_topic_question_unsupported(self):
        self.assertEqual(self.p.decide("what's the weather", snap(SCREEN1, [])).kind, "unsupported")

    def test_malayalam_question_accepted(self):
        s = snap(SCREEN1, [field("c01", "classification", False, "AXPopUpButton")])
        self.assertEqual(self.p.decide("നെല്ല് നഷ്ടം അപേക്ഷ", s).kind, "point")

    def test_unknown_screen(self):
        self.assertEqual(self.p.decide(ASK, snap("Login", [])).kind, "unsupported")

    def test_upload_then_add_detected_from_notes(self):
        crop = [field("c1", "insured-crop", True, "AXPopUpButton"), field("c2", "crop-stage", True, "AXPopUpButton"),
                field("c3", "quantity-applied", True), field("c4", "crop-image", None, "AXButton"),
                field("c6", "add-crop", None, "AXButton"), field("c8", "next", None, "AXButton")]
        before = snap("Crop Information", crop + [note("c5", "crop-image-file", "No file chosen"),
                                                  note("c7", "added-details", "Added Details: none")])
        self.assertEqual(self.p.decide(ASK, before).control_id, "c4")
        chosen = snap("Crop Information", crop + [note("c5", "crop-image-file", "Chosen: TEST.jpg"),
                                                  note("c7", "added-details", "Added Details: none")])
        self.assertEqual(self.p.decide(ASK, chosen).control_id, "c6")

    def test_declaration_then_complete(self):
        view = "Application View (training draft)"
        s = snap(view, [field("c1", "declaration", False, "AXCheckBox")])
        self.assertEqual(self.p.decide(ASK, s).control_id, "c1")
        done = Snapshot("s1", time.time(), "b", 1, "w", WIN, (
            Control("c00", "AXStaticText", view, (448, 193, 322, 26), identifier="screen-title"),
            Control("c99", "AXStaticText", "Training draft complete — declaration ticked.", (448, 647, 574, 18),
                    identifier="status"),
            field("c1", "declaration", True, "AXCheckBox")))
        self.assertEqual(self.p.decide(ASK, done).kind, "complete")


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
