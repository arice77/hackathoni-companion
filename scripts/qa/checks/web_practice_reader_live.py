"""Live Accessibility read of the web practice page in Safari: step ids found on every screen,
no browser-chrome controls, no typed or chosen values leaked into labels.

The test-only driver (scripts/drive_web_practice.py) types and presses, only on our own page.
"""
import time

from _common import result, wait_for
import _web

FEATURE = "web-support"
INTERACTIVE = {"AXButton", "AXTextField", "AXPopUpButton", "AXCheckBox", "AXLink", "AXMenuButton",
               "AXRadioButton", "AXComboBox", "AXTextArea"}
CHROME_WORDS = ("address", "reload", "sidebar", "share", "back", "forward", "tab overview", "search or enter",
                "new tab", "downloads", "show tab", "close tab", "private")
SCREEN_FIELD_VALUES = ("QA-CANARY", "Lantern", "Alappuzha", "Retail")  # typed or chosen values: never in labels


def run():
    from companion import reader
    from companion.tasks import load
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    drive = _web.load_drive()
    task = load("web_practice")
    err = _web.open_fresh_page(drive)
    if err:
        return [result(FEATURE, "web practice page opens in Safari", "fail", "live-machine", err)]
    out = []
    try:
        seen = []  # (screen, snapshot)

        read_ms = []

        def snap():
            def one():
                t0 = time.perf_counter()
                try:
                    got = reader.snapshot(reader.SAFARI)
                except reader.ReaderError:
                    return None
                read_ms.append(1000 * (time.perf_counter() - t0))
                return got
            return wait_for(one, seconds=8)

        def settle(title):
            # the page redraws after a press; wait until the heading shows the new screen
            def ready():
                s = snap()
                head = next((c for c in (s.controls if s else ()) if c.identifier == "screen-title"), None)
                return s if head and head.label.startswith(title) else None
            return wait_for(ready, seconds=8, every=0.3)

        # --- screen 1: type a canary value, then choose via the sample button
        s1 = settle(task.screens[0].title_prefix)
        if s1 is None:
            return out + [result(FEATURE, "snapshot", "fail", "live-machine", "no readable practice page snapshot")]
        before_typed = {c.identifier: c.filled for c in s1.controls if c.identifier}
        seen.append((task.screens[0], s1))
        drive.act("business-name")
        time.sleep(0.6)
        s1b = snap()
        seen.append((task.screens[0], s1b))
        name_ctl = next((c for c in s1b.controls if c.identifier == "business-name"), None)
        drive.act("sample-details")
        time.sleep(0.6)
        s1c = snap()
        seen.append((task.screens[0], s1c))
        filled_after = {c.identifier: c.filled for c in s1c.controls if c.identifier}
        out.append(result(FEATURE, "filled flags follow input (no values)",
                          "pass" if (before_typed.get("business-name") is False and name_ctl and name_ctl.filled is True
                                     and filled_after.get("district") and filled_after.get("category")) else "fail",
                          "live-machine",
                          f"empty={ {k: v for k, v in before_typed.items() if v is not None} } "
                          f"typed name filled={name_ctl.filled if name_ctl else None} after sample={ {k: v for k, v in filled_after.items() if v is not None} }"))

        # --- screens 2 and 3
        drive.act("details-next")
        s2 = settle(task.screens[1].title_prefix)
        seen.append((task.screens[1], s2))
        if s2:
            drive.act("attach-sample")
            time.sleep(0.6)
            seen.append((task.screens[1], snap()))
            drive.act("documents-next")
        s3 = settle(task.screens[2].title_prefix)
        seen.append((task.screens[2], s3))
        if s3:
            drive.act("declaration")
            time.sleep(0.6)
            seen.append((task.screens[2], snap()))

        # --- claims
        missing = []
        for screen, s in seen:
            if s is None:
                continue
            ids = {c.identifier for c in s.controls if c.identifier}
            need = {st.identifier for st in screen.steps} | ({screen.final.identifier} if screen.final else set()) | {"screen-title", "status"}
            gone = need - ids
            if gone:
                missing.append((screen.title_prefix, sorted(gone)))
        got_screens = [sc.title_prefix for sc, s in seen if s is not None]
        unread = [sc.title_prefix for sc, s in seen if s is None]
        out.append(result(FEATURE, "step ids found on all 3 screens",
                          "fail" if missing or unread or {"Business Details", "Documents", "Review"} - set(got_screens) else "pass",
                          "live-machine",
                          f"missing {missing}; unreadable {unread}" if missing or unread else
                          f"{len(seen)} snapshots over 3 screens; every task step id plus screen-title and status present"))

        chrome, no_id, out_of_window = [], [], []
        for _, s in seen:
            if s is None:
                continue
            wx, wy, ww, wh = s.window_frame
            for c in s.controls:
                low = c.label.lower()
                if c.role in INTERACTIVE and not c.identifier:
                    no_id.append((c.role, c.label[:30]))
                if c.role in INTERACTIVE and any(w in low for w in CHROME_WORDS):
                    chrome.append((c.identifier, c.label[:30]))
                x, y, w, h = c.frame
                if x < wx - 1 or y < wy - 1 or x + w > wx + ww + 1 or y + h > wy + wh + 1:
                    out_of_window.append(c.identifier or c.label[:30])
        bad = no_id or chrome or out_of_window
        out.append(result(FEATURE, "no browser-chrome controls", "fail" if bad else "pass", "live-machine",
                          f"interactive without DOM id {sorted(set(no_id))}; chrome-like {chrome}; outside window {out_of_window}"
                          if bad else "every interactive control has a DOM id, none chrome-like, all inside the window"))

        leaked = [(c.identifier, c.label[:40]) for _, s in seen if s for c in s.controls
                  if any(v in c.label for v in SCREEN_FIELD_VALUES)]
        out.append(result(FEATURE, "typed/chosen values not leaked", "fail" if leaked else "pass", "live-machine",
                          f"values found in labels: {leaked}" if leaked else
                          "canary name, sample name, district and category absent from every label"))
        ms = sorted(read_ms)
        out.append(result(FEATURE, "Safari page read latency", "pass" if ms and ms[-1] < 250 else "fail", "live-machine",
                          f"{len(ms)} reads, median {ms[len(ms)//2]:.0f} ms, max {ms[-1]:.0f} ms (limit 250)" if ms else "no reads"))
    finally:
        _web.close_practice_windows()
    return out
