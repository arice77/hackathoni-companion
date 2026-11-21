import time
import unittest

from companion.contracts import Control, Snapshot
from companion.planner import ScriptedPlanner
from companion.tasks import load
from companion.validator import validate


QUESTION = "Help me fill out this business form"
FRAME = (25.0, 30.0, 80.0, 24.0)


def snapshot(title, states=None, note="No sample attached", status="Ready for practice"):
    task = load("web_practice")
    screen = next(screen for screen in task.screens if screen.title_prefix == title)
    controls = [Control("title", "AXHeading", title, FRAME, identifier="screen-title"),
                Control("status", "AXStaticText", status, FRAME, identifier="status")]
    for step in (*screen.steps, screen.final):
        role = "AXButton" if step.done_note or step == screen.final else "AXTextField"
        controls.append(Control(step.identifier, role, "", FRAME, identifier=step.identifier,
                                filled=(states or {}).get(step.identifier)))
        if step.done_note and note is not None:
            controls.append(Control("note", "AXStaticText", note, FRAME, identifier=step.done_note))
    return Snapshot("practice-snapshot", time.time(), task.bundle_id, 10, "Business Form Practice",
                    (0.0, 0.0, 800.0, 600.0), tuple(controls))


class WebPracticeTaskTests(unittest.TestCase):
    def setUp(self):
        self.planner = ScriptedPlanner("web_practice")

    def assert_points(self, snap, identifier, question=QUESTION):
        decision = self.planner.decide(question, snap)
        self.assertEqual((decision.kind, decision.control_id), ("point", identifier))
        self.assertEqual(validate(decision, snap), (True, "ok"))

    def test_first_step_per_screen(self):
        for title, identifier in (("Business Details", "business-name"), ("Documents", "attach-sample"),
                                  ("Review", "declaration")):
            with self.subTest(title=title):
                self.assert_points(snapshot(title), identifier)

    def test_business_fields_and_next(self):
        states = {"business-name": True}
        self.assert_points(snapshot("Business Details", states), "district")
        states["district"] = True
        self.assert_points(snapshot("Business Details", states), "category")
        states["category"] = True
        self.assert_points(snapshot("Business Details", states), "details-next")

    def test_attach_is_complete_only_with_note(self):
        self.assert_points(snapshot("Documents", note="Sample attached · no file uploaded"), "documents-next")
        self.assertEqual(self.planner.decide(QUESTION, snapshot("Documents", note=None)).kind, "unsupported")

    def test_save_after_declaration_and_complete_after_receipt_status(self):
        self.assert_points(snapshot("Review", {"declaration": True}), "save")
        decision = self.planner.decide(QUESTION, snapshot("Review", status="Training complete · receipt saved"))
        self.assertEqual((decision.kind, decision.control_id), ("complete", None))
        self.assertEqual(self.planner.task.receipt_file, "web-practice-complete.json")

    def test_malayalam_manglish_and_off_topic(self):
        snap = snapshot("Business Details")
        for question in ("ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?", "apeksha engane poorippikkam?"):
            self.assert_points(snap, "business-name", question)
        self.assertEqual(self.planner.decide("Is it raining outside?", snap).kind, "unsupported")


if __name__ == "__main__":
    unittest.main()
