import json
import unittest
from dataclasses import asdict
from hashlib import sha256
from unittest.mock import patch

from companion import reader


VIEWPORT = (0, 0, 500, 400)
VIDEO = "abcTest_X12"
HANDLE = "@DemoChannel"
PLAYLIST = "PL-DemoList123"


def fake_snapshot(host, links, *, hidden=(), headings=(), frames=None):
    url = f"https://{host}/results?search_query=unexported-search"
    nodes = {"page": {"AXRole": "AXWebArea", "AXURL": url,
                      "AXChildren": [f"heading-{name}" if name in headings else name for name in links]}}
    nodes.update({
        name: {"AXRole": "AXLink", "AXTitle": label, "AXDOMIdentifier": dom_id, "AXURL": destination}
        for name, (label, dom_id, destination) in links.items()
    })
    for name in headings:
        nodes[f"heading-{name}"] = {"AXRole": "AXHeading", "AXChildren": [name]}
    link_url_reads = []

    def get(el, name):
        if el != "page" and name == "AXURL":
            link_url_reads.append(el)
        return nodes[el].get(name)

    def frame(el, _get):
        if el == "page":
            return VIEWPORT
        return (10, 450, 100, 20) if el in hidden else (frames or {}).get(el, (10, 20, 100, 20))

    view = reader._WebView("page", VIEWPORT, VIEWPORT, url, ())
    with patch.object(reader, "_frame", side_effect=frame):
        snap = reader._read_web_snapshot(view, reader.SAFARI, 123, get)
    return snap, link_url_reads


def marker(kind, key):
    return f"youtube-{kind}:{sha256(key.encode()).hexdigest()[:10]}"


class YouTubeLinkTests(unittest.TestCase):
    def test_disambiguates_identical_visible_titles_by_destination(self):
        label = "Same Malayalam song title"
        snap, reads = fake_snapshot("www.youtube.com", {
            "video": (label, VIDEO, f"https://www.youtube.com/watch?feature=search&v={VIDEO}"),
            "handle": (label, HANDLE, f"/{HANDLE}/videos"),
            "channel": (label, "UC-DemoChannel", "/channel/UC-DemoChannel/featured"),
            "playlist": (label, PLAYLIST, f"/playlist?list={PLAYLIST}&tracking=not-exported"),
            "outside": (label, "external-id", f"https://youtube.com.example.org/watch?v={VIDEO}"),
            "below": (label, "hidden-id", f"/watch?v={VIDEO}"),
        }, hidden={"below"})
        self.assertEqual([control.label for control in snap.controls], [label] * 5)
        for control, target in zip(snap.controls, [
            marker("watch", VIDEO), marker("channel", HANDLE.casefold()),
            marker("channel", "UC-DemoChannel"), marker("playlist", PLAYLIST),
        ], strict=False):
            self.assertRegex(control.identifier, rf"^{target}:[0-9a-f]{{10}}$")
        self.assertIsNone(snap.controls[-1].identifier)
        self.assertEqual(reads, ["video", "handle", "channel", "playlist", "outside"])

    def test_watch_and_shorts_produce_the_same_marker_across_snapshots(self):
        first, _ = fake_snapshot("youtube.com", {
            "video": ("Title", VIDEO, f"/watch?t=9&v={VIDEO}&list={PLAYLIST}"),
        })
        second, _ = fake_snapshot("m.youtube.com", {
            "other": ("Channel", "placeholder", "/@other"),
            "short": ("Title", "new-id", f"https://m.youtube.com/shorts/{VIDEO}?feature=shorts"),
        })
        self.assertNotEqual(first.controls[0].id, second.controls[1].id)
        self.assertEqual(first.controls[0].identifier, second.controls[1].identifier)

    def test_title_and_thumbnail_have_distinct_keys_when_the_same_label_moves(self):
        video_url = f"/watch?v={VIDEO}"
        title = ("Same title", "video-title", video_url)
        thumbnail = ("Same title", "thumbnail", video_url)
        first, _ = fake_snapshot("www.youtube.com", {"image": thumbnail, "title": title})
        second, _ = fake_snapshot("www.youtube.com", {"title": title, "image": thumbnail},
                                  frames={"title": (30, 40, 130, 20), "image": (5, 70, 180, 90)})
        title_only, _ = fake_snapshot("www.youtube.com", {"image": thumbnail, "title": title}, hidden={"image"})
        target = marker("watch", VIDEO)
        image_id, title_id = (control.identifier for control in first.controls)
        self.assertRegex(image_id, rf"^{target}:b[0-9a-f]{{9}}$")
        self.assertRegex(title_id, rf"^{target}:a[0-9a-f]{{9}}$")
        self.assertEqual([control.identifier for control in second.controls], [title_id, image_id])
        self.assertEqual(title_only.controls[0].identifier, title_id)

    def test_heading_ancestry_can_mark_title_without_dom_identifier(self):
        snap, _ = fake_snapshot("m.youtube.com", {
            "title": ("A video title", None, f"/watch?v={VIDEO}"),
        }, headings={"title"})
        link = next(control for control in snap.controls if control.role == "AXLink")
        self.assertRegex(link.identifier, rf"^{marker('watch', VIDEO)}:a[0-9a-f]{{9}}$")

    def test_same_kind_duplicate_anchors_also_get_distinct_identifiers(self):
        cases = (
            ("watch", VIDEO, f"/watch?v={VIDEO}"),
            ("channel", HANDLE.casefold(), f"/{HANDLE}"),
            ("playlist", PLAYLIST, f"/playlist?list={PLAYLIST}"),
        )
        for kind, key, url in cases:
            with self.subTest(kind=kind):
                anchor = ("Same label", None, url)
                snap, _ = fake_snapshot("youtube.com", {"first": anchor, "second": anchor})
                first, second = (control.identifier for control in snap.controls)
                self.assertRegex(first, rf"^{marker(kind, key)}:c[0-9a-f]{{9}}$")
                self.assertRegex(second, rf"^{marker(kind, key)}:c[0-9a-f]{{9}}$")
                self.assertNotEqual(first, second)

    def test_raw_destinations_and_tokens_do_not_leave_the_reader(self):
        watch_url = f"https://www.youtube.com/watch?v={VIDEO}&t=123"
        snap, _ = fake_snapshot("www.youtube.com", {
            "absolute": (f"Watch {watch_url}", watch_url, watch_url),
            "token": (f"Watch {VIDEO}", VIDEO, watch_url),
            "handle": (f"Channel {HANDLE.upper()}", HANDLE, f"/{HANDLE}"),
            "relative": (f"List /playlist?list={PLAYLIST}", PLAYLIST, f"/playlist?list={PLAYLIST}"),
        })
        self.assertEqual([control.label for control in snap.controls], ["Watch", "Watch", "Channel", "List"])
        payload = json.dumps(asdict(snap)).casefold()
        for sensitive in (VIDEO, HANDLE, PLAYLIST, watch_url, "unexported-search"):
            self.assertNotIn(sensitive.casefold(), payload)

    def test_other_sites_do_not_read_link_destinations(self):
        snap, reads = fake_snapshot("example.org", {
            "video": ("A title", "fixture-link", f"https://www.youtube.com/watch?v={VIDEO}"),
        })
        self.assertEqual(reads, [])
        self.assertEqual(snap.controls[0].identifier, "fixture-link")
