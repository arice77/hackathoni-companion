import unittest

from companion.overlay.geometry import display_index, place_note, to_appkit


class GeometryTests(unittest.TestCase):
    def test_primary_height_and_fractional_points(self):
        self.assertEqual(to_appkit((32.5, 100, 72, 22.5), 900), (32.5, 777.5, 72, 22.5))

    def test_above_and_left(self):
        screens = [(0, 0, 1440, 900), (0, 900, 1200, 800), (-1600, -100, 1600, 1000)]
        for ax, expected, display in [
            ((90, -250, 100, 30), (90, 1120, 100, 30), 1),
            ((-270, 150, 100, 30), (-270, 720, 100, 30), 2),
        ]:
            with self.subTest(ax=ax):
                converted = to_appkit(ax, screens[0][3])
                self.assertEqual(converted, expected)
                self.assertEqual(display_index(converted, screens), display)

    def test_target_straddles_two_displays(self):
        self.assertEqual(display_index((-40, 110, 50, 20),
                                      [(0, 0, 800, 600), (-800, 0, 800, 600)]), 1)

    def test_all_edges_leave_card_and_target_visible(self):
        bounds = (0, 25, 800, 440)
        for target in [(330, 25, 80, 30), (330, 435, 80, 30),
                       (0, 300, 80, 30), (720, 300, 80, 30)]:
            with self.subTest(target=target):
                x, y, w, h = target
                nx, ny, nw, nh = place_note(target, bounds, 240, 90)
                self.assertGreaterEqual(nx, 8)
                self.assertGreaterEqual(ny, 33)
                self.assertLessEqual(nx+nw, 792)
                self.assertLessEqual(ny+nh, 457)
                self.assertTrue(ny >= y+h if y == 25 else ny+nh <= y)
                if x == 0:
                    self.assertGreater(nx, x)
                if x == 720:
                    self.assertLess(nx+nw, x+w)

    def test_tall_target_uses_horizontal_gap(self):
        for target in [(15, 10, 80, 450), (705, 10, 80, 450)]:
            nx, _, nw, _ = place_note(target, (0, 0, 800, 480), 220, 90)
            self.assertTrue(nx >= target[0]+80 or nx+nw <= target[0])
