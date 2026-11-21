"""Live Accessibility read of the AIMS training fixture: controls found, typed values withheld."""
from _common import result, sh, wait_for

FEATURE = "reader"
BUNDLE = "in.hackathoni.crop-loss-training"
EXPECTED = {"screen-title", "classification", "service", "next", "krishibhavan"}


def run():
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine",
                       "this process is not Accessibility-trusted; run from a trusted terminal")]
    sh("sh", "scripts/restart_training.sh")
    if not wait_for(lambda: reader.find_app(BUNDLE)):
        return [result(FEATURE, "fixture launch", "fail", "live-machine", "training app did not start")]
    snap = wait_for(lambda: _try(reader), seconds=8)
    if snap is None:
        return [result(FEATURE, "snapshot", "fail", "live-machine", "no readable window")]
    idents = {c.identifier for c in snap.controls if c.identifier}
    missing = EXPECTED - idents
    leaked = [c.id for c in snap.controls if "Pulincunnoo" in c.label]  # prefilled field value
    bad_rects = [c.id for c in snap.controls if c.frame[2] <= 0 or c.frame[3] <= 0]
    return [
        result(FEATURE, "expected controls found", "fail" if missing else "pass", "live-machine",
               f"{len(snap.controls)} controls; missing {sorted(missing)}" if missing else f"{len(snap.controls)} controls"),
        result(FEATURE, "input values withheld", "fail" if leaked else "pass", "live-machine",
               f"value leaked in {leaked}" if leaked else "prefilled Krishibhavan value absent from labels"),
        result(FEATURE, "positive rectangles", "fail" if bad_rects else "pass", "live-machine",
               str(bad_rects) if bad_rects else "all frames positive"),
    ]


def _try(reader):
    try:
        return reader.snapshot(BUNDLE)
    except reader.ReaderError:
        return None
