"""Opt-in Safari walk; unit discovery tests the send guard without opening Gmail."""

import argparse
import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
import traceback
import unittest
from pathlib import Path

from companion import reader
from companion.sites.gmail import ATTACH, BODY, COMPOSE, PACK, SEND, SUBJECT, TO
from companion.validator import validate

ROOT = Path(__file__).resolve().parents[1]
MAIL = "https://mail.google.com/mail/u/0/"
PLACEHOLDER = "me@example.invalid"
SUBJECT_TEXT = "HackaThoni companion test"
BODY_TEXT = "This is a short test of the email guidance. No reply needed."
ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ENV_KEYS = {"QA_GMAIL_TO", "QA_GMAIL_ALLOWED"}


class WalkStopped(RuntimeError):
    pass


def recipient_from_config(environ, env_path=ROOT / ".env"):
    config = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.strip().removeprefix("export ").partition("=")
            key, value = key.strip(), value.strip()
            if key in ENV_KEYS and separator:
                if len(value) >= 2 and value[0] in "'\"" and value[0] == value[-1]:
                    value = value[1:-1].strip()
                config[key] = value
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        raise WalkStopped("Could not read the repo-root QA configuration.") from None
    config.update({key: environ[key].strip() for key in ENV_KEYS if key in environ})
    target = config.get("QA_GMAIL_TO", "")
    allowed = {item.strip().casefold() for item in config.get("QA_GMAIL_ALLOWED", "").split(",") if item.strip()}
    if not ADDRESS.fullmatch(target) or target.casefold().endswith(".invalid") or target.casefold() not in allowed:
        raise WalkStopped("Send refused: the QA recipient is missing, invalid, or not allowlisted.")
    return target


class SendOnce:
    def __init__(self, recipient):
        self.recipient = recipient.casefold()
        self.attempted = False

    def press(self, observed, approved, action):
        if self.attempted or approved.casefold() != self.recipient or observed != {self.recipient}:
            raise WalkStopped("Send refused: recipient verification or one-attempt guard failed.")
        self.attempted = True
        return action()


class GmailSendGuardTests(unittest.TestCase):
    def test_config_reads_only_approved_keys_and_prefers_the_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "export QA_GMAIL_TO='one@example.test'\n"
                "QA_GMAIL_ALLOWED=\"one@example.test, two@example.test\"\n"
                "UNRELATED_VALUE=ignore\n",
                encoding="utf-8",
            )
            self.assertEqual(recipient_from_config({}, env_path), "one@example.test")
            self.assertEqual(recipient_from_config({"QA_GMAIL_TO": "two@example.test"}, env_path),
                             "two@example.test")
            with self.assertRaises(WalkStopped):
                recipient_from_config({"QA_GMAIL_ALLOWED": ""}, env_path)

    def test_send_requires_a_single_allowlisted_address(self):
        missing = ROOT / ".context" / "nonexistent-unit-test-env"
        for target in ("", PLACEHOLDER, "a@example.test,b@example.test", "other@example.test"):
            with self.subTest(target=target), self.assertRaises(WalkStopped):
                recipient_from_config({"QA_GMAIL_TO": target, "QA_GMAIL_ALLOWED": "a@example.test, me@example.invalid"},
                                      missing)
        self.assertEqual(recipient_from_config({"QA_GMAIL_TO": "A@example.test", "QA_GMAIL_ALLOWED": "a@example.test"},
                                               missing), "A@example.test")

    def test_send_checks_committed_addresses_and_never_retries(self):
        guard = SendOnce("a@example.test")
        called = []
        for observed in (set(), {"other@example.test"}, {"a@example.test", "other@example.test"}):
            with self.assertRaises(WalkStopped):
                guard.press(observed, "a@example.test", lambda: called.append(True))
        self.assertEqual(called, [])
        with self.assertRaises(ValueError):
            guard.press({"a@example.test"}, "a@example.test", lambda: int("failed AX call"))
        with self.assertRaises(WalkStopped):
            guard.press({"a@example.test"}, "a@example.test", lambda: called.append(True))
        self.assertTrue(guard.attempted)
        self.assertEqual(called, [])


def osa(source, *argv):
    result = subprocess.run(["osascript", "-", *argv], input=source, text=True, capture_output=True, timeout=8)
    if result.returncode:
        raise WalkStopped("Safari automation failed.")
    return result.stdout.strip()


class GmailWalk:
    def __init__(self, window, overlay):
        self.window = window
        self.overlay = overlay
        self.guide = PACK.start_guidance("എനിക്ക് ഒരു ഇമെയിൽ അയയ്ക്കണം")
        self.pid = None
        self.draft_fields = []

    def guard(self):
        owned = osa('''on run argv
            tell application id "com.apple.Safari"
                if (id of front window as text) is not item 1 of argv then return false
                if (count of tabs of front window) is not 1 then return false
                return (URL of current tab of front window) starts with (item 2 of argv)
            end tell
        end run''', self.window, MAIL)
        if owned != "true":
            raise WalkStopped("The test window is not Safari's selected Gmail window.")

    def input_guard(self):
        self.guard()
        if reader.frontmost_bundle_id() != reader.SAFARI:
            raise WalkStopped("Safari is not the active app; no input was posted.")

    def page(self):
        self.guard()
        if self.pid is None:
            raise WalkStopped("No verified Safari process for the owned window.")
        pid = self.pid
        root = reader.AX.AXUIElementCreateApplication(pid)
        area, _, viewport, url = reader._selected_web_page(root, reader._attr, page_url_prefix=MAIL)
        return pid, root, area, viewport, url

    def snapshot(self):
        reason = "not yet available"
        for _attempt in range(18):
            self.guard()
            try:
                if self.pid is None:
                    snap = reader.snapshot(reader.SAFARI, page_url_prefix=MAIL)
                else:
                    root = reader.AX.AXUIElementCreateApplication(self.pid)
                    get = reader._web_getter(time.monotonic())
                    view = reader._web_view(root, get, None, MAIL)
                    snap = reader._read_web_snapshot(view, reader.SAFARI, self.pid, get)
                self.pid = snap.app_pid
                return snap
            except reader.ReaderError as exc:
                reason = str(exc)
                time.sleep(.25)
        raise WalkStopped(f"No readable Gmail snapshot in the owned window: {reason}")

    def wait(self, predicate):
        for _attempt in range(22):
            snap = self.snapshot()
            if predicate(snap):
                return snap
            time.sleep(.25)
        raise WalkStopped("Did not reach the expected draft state.")

    def next(self, text="അടുത്തത്"):
        self.guide.skip_current(text)

    def raw_controls(self):
        pid, root, area, viewport, url = self.page()
        if reader.GMAIL_THREAD.fullmatch(url.partition("#")[2].partition("?")[0]):
            raise WalkStopped("A conversation was unexpectedly opened.")
        leaves = (reader.WEB_LEAVES - {"AXComboBox"}) | {"AXTable", "AXLayoutTable", "AXCell"} | reader.GMAIL_ROW_ROLES
        return pid, root, viewport, reader._walk(area, reader._attr, reader.MAX_WEB_ELEMENTS, leaves)

    def point(self, expected):
        from Foundation import NSDate, NSRunLoop

        snap = self.wait(lambda current: expected.target(current) is not None)
        decision = self.guide.decide(snap)
        target = snap.control(decision.control_id)
        if not validate(decision, snap)[0] or target is None or not expected.matches(target):
            raise WalkStopped(f"The guide did not point at {expected.label} (decision: {decision.kind}).")
        self.overlay.show(target.frame, decision.instruction)
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.3))
        pid, root, viewport, nodes = self.raw_controls()
        matches = []
        for el, role, _parent in nodes:
            if role != target.role or reader._gmail_label(el, role, reader._attr) != target.label:
                continue
            frame = reader._frame(el)
            if frame is not None and reader._intersection(frame, viewport) == target.frame:
                matches.append(el)
        if len(matches) != 1:
            raise WalkStopped("The pointer did not resolve to a unique Gmail control.")
        print(f"Validated pointer: {expected.label}", flush=True)
        return pid, root, matches[0]

    def press(self, node):
        self.input_guard()
        return reader.AX.AXUIElementPerformAction(node, "AXPress")

    def type_at(self, step, text, *, commit_recipient=False):
        import Quartz

        pid, root, node = self.point(step)
        self.input_guard()
        reader.AX.AXUIElementSetAttributeValue(node, "AXFocused", True)
        time.sleep(.15)
        editable = reader._attr(root, "AXFocusedUIElement")
        focus = editable
        for _attempt in range(4):
            if focus is None or focus == node:
                break
            focus = reader._attr(focus, "AXParent")
        if focus != node:
            raise WalkStopped("Could not confirm focus on the pointed draft field.")
        if any(reader._attr(field, "AXValue") not in (None, "", "\n") for field in (node, editable)):
            raise WalkStopped("The pointed test field was not empty.")
        for start in range(0, len(text), 12):
            self.input_guard()
            chunk = text[start:start + 12]
            for keydown in (True, False):
                event = Quartz.CGEventCreateKeyboardEvent(None, 0, keydown)
                Quartz.CGEventKeyboardSetUnicodeString(event, len(chunk), chunk)
                Quartz.CGEventPostToPid(pid, event)
        time.sleep(.35)
        if not self.has_text((node, editable), text):
            self.input_guard()
            if reader._attr(root, "AXFocusedUIElement") != editable:
                raise WalkStopped("Focus changed before verifying the test text.")
            reader.AX.AXUIElementSetAttributeValue(editable, "AXValue", text)
            time.sleep(.25)
            if not self.has_text((node, editable), text):
                raise WalkStopped("Could not verify that the pointed field received the test text.")
        if commit_recipient:
            self.input_guard()
            for keydown in (True, False):
                Quartz.CGEventPostToPid(pid, Quartz.CGEventCreateKeyboardEvent(None, 36, keydown))
        time.sleep(.5)
        if not commit_recipient:
            self.draft_fields.append(((node, editable), text))
        self.next()

    @staticmethod
    def has_text(nodes, text):
        return any(isinstance(value := reader._attr(node, "AXValue"), str) and value.strip() == text for node in nodes)

    def committed_recipients(self):
        snap = self.snapshot()
        field = TO.target(snap)
        if any(control.label in {"Cc", "Bcc"} and control.role in reader.GMAIL_FIELD_ROLES
               for control in snap.controls):
            raise WalkStopped("Could not verify an isolated To row.")
        if field is None:
            return set()
        _pid, _root, _viewport, nodes = self.raw_controls()
        inputs = []
        for el, role, _parent in nodes:
            if role == TO.role and reader._gmail_label(el, role, reader._attr) == TO.label:
                inputs.append(el)
        if len(inputs) != 1 or reader._attr(inputs[0], "AXValue") not in (None, ""):
            raise WalkStopped("The recipient was not committed as a chip.")
        row = inputs[0]
        parent = reader._attr(row, "AXParent")
        center = field.frame[1] + field.frame[3] / 2
        for _attempt in range(7):
            if parent is None:
                break
            box = reader._frame(parent)
            if box is not None and box[1] <= center <= box[1] + box[3]:
                if box[3] > 85:
                    break
                row = parent
            parent = reader._attr(parent, "AXParent")
        addresses = set()
        leaves = reader.WEB_LEAVES | {"AXMenu", "AXListBox", "AXMenuItem", "AXTable", "AXLayoutTable"}
        role_count = 0
        for el, role, _parent in reader._walk(row, reader._attr, 100, leaves):
            if role in reader.GMAIL_FIELD_ROLES | {"AXMenu", "AXListBox", "AXMenuItem"}:
                continue
            box = reader._frame(el)
            if box is None or not box[1] - 8 <= center <= box[1] + box[3] + 8:
                continue
            role_count += 1
            for attr in ("AXTitle", "AXDescription", "AXLabel", "AXHelp", "AXValue", "AXURL"):
                value = reader._attr(el, attr)
                if attr == "AXURL" and value is not None:
                    value = str(value)
                if isinstance(value, str):
                    addresses.update(address.casefold() for address in ADDRESS.findall(value))
        if not addresses:
            print(f"No address exposed on the committed To row ({role_count} non-input AX nodes).", flush=True)
        return addresses

    def confirm_recipient(self, expected):
        observed = self.committed_recipients()
        if observed:
            return observed
        self.input_guard()
        script = r'''(() => {
            const address = __EXPECTED__;
            const labels = new Set(['to', 'to recipients', 'recipients', 'add recipients']);
            const subjects = [...document.querySelectorAll('input[name="subjectbox"]')].filter(field =>
                field.getClientRects().length && field.value === __SUBJECT__);
            if (subjects.length !== 1) return false;
            const editor = subjects[0].closest('[role="dialog"]');
            if (!editor) return false;
            const pending = [...editor.querySelectorAll('input[aria-label]')].some(field =>
                labels.has(field.getAttribute('aria-label').trim().toLowerCase()) && field.value.trim());
            if (pending) return false;
            const found = new Set();
            for (const chip of editor.querySelectorAll('[email], [data-email], [data-hovercard-id]')) {
                if (chip.closest('[role="listbox"], [role="menu"]')) continue;
                for (const attribute of ['email', 'data-email', 'data-hovercard-id']) {
                    const value = chip.getAttribute(attribute)?.trim().toLowerCase();
                    if (value && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) found.add(value);
                }
            }
            return found.size === 1 && found.has(address);
        })()'''.replace("__EXPECTED__", json.dumps(expected.casefold())).replace("__SUBJECT__", json.dumps(SUBJECT_TEXT))
        quoted = script.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        try:
            verified = osa(f'''on run argv
                tell application id "com.apple.Safari"
                    if (id of front window as text) is not item 1 of argv then return false
                    if not ((URL of current tab of front window) starts with (item 2 of argv)) then return false
                    return do JavaScript "{quoted}" in current tab of front window
                end tell
            end run''', self.window, MAIL)
        except WalkStopped:
            return set()
        return {expected.casefold()} if verified == "true" else set()


def main():
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from companion.app import make_overlay

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="send exactly once only to the configured allowlisted recipient")
    options = parser.parse_args()
    send = None
    try:
        recipient = recipient_from_config(os.environ) if options.send else PLACEHOLDER
        send = SendOnce(recipient) if options.send else None
        with open("/tmp/hackathoni-companion-qa.lock", "a+") as lock:
            if subprocess.run(["pgrep", "-f", "/Python scripts/qa/[r]un.py( |$)"], capture_output=True).returncode == 0:
                raise WalkStopped("QA active; did not open Gmail.")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise WalkStopped("Shared browser lock is held; did not open Gmail.") from None
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            overlay, _kind = make_overlay()
            window = osa('''on run argv
                tell application id "com.apple.Safari"
                    set existingIDs to id of every window
                    make new document with properties {URL:item 1 of argv}
                    activate
                    set createdID to id of front window
                    if createdID is not in existingIDs then return createdID
                end tell
            end run''', MAIL + "#inbox")
            if not window.isdigit():
                raise WalkStopped("The dedicated Gmail window could not be identified.")
            try:
                time.sleep(2)
                walk = GmailWalk(window, overlay)
                inbox = walk.wait(lambda snap: any(control.role == "AXTable" for control in snap.controls))
                if any(step.target(inbox) for step in (TO, SUBJECT, BODY, SEND)):
                    raise WalkStopped("An existing editor is visible; no controls were operated.")
                _, _, compose = walk.point(COMPOSE)
                if walk.press(compose) != 0:
                    raise WalkStopped("Compose could not be opened.")
                walk.type_at(TO, recipient, commit_recipient=True)
                walk.type_at(SUBJECT, SUBJECT_TEXT)
                walk.type_at(BODY, BODY_TEXT)
                walk.point(ATTACH)
                walk.next("skip")
                _, _, send_button = walk.point(SEND)
                if send is None:
                    print("Draft-only walk stopped at Send; nothing sent.")
                else:
                    if len(walk.draft_fields) != 2 or not all(walk.has_text(fields, text)
                                                            for fields, text in walk.draft_fields):
                        raise WalkStopped("The verified test subject or body changed; no send attempted.")
                    observed = walk.confirm_recipient(recipient)
                    if observed != {recipient.casefold()}:
                        raise WalkStopped("The committed recipient could not be independently verified; no send attempted.")
                    status = send.press(observed, recipient_from_config(os.environ),
                                        lambda: walk.press(send_button))
                    if status != 0:
                        raise WalkStopped("Send returned an uncertain result; it was not retried.")
                    walk.wait(lambda snap: not any(step.target(snap) for step in (TO, SUBJECT, BODY, SEND)))
                    print("One allowlisted Send press accepted; composer closed. No other mail opened.")
            finally:
                overlay.hide()
                osa('''on run argv
                    tell application id "com.apple.Safari"
                        set testID to item 1 of argv as integer
                        if (count of tabs of window id testID) is 1 then close window id testID
                    end tell
                end run''', window)
    except WalkStopped as exc:
        print(str(exc))
        print("Send attempted:", bool(send and send.attempted))
        return 1
    except Exception as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        location = frames[-1]
        print(f"Gmail walk stopped: {type(exc).__name__} in {location.name} at line {location.lineno}. "
              f"Send attempted: {bool(send and send.attempted)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
