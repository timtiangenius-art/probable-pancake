import json
import unittest

from tiktok_plot import build_prompt, build_storyboard, parse_plot
from tiktok_plot.parser import ParseError


class ParseTests(unittest.TestCase):
    def test_one_line_is_one_scene(self):
        plot = parse_plot("first line\nsecond line\nthird line\n")
        self.assertEqual([s.text for s in plot.scenes], ["first line", "second line", "third line"])
        self.assertEqual([s.index for s in plot.scenes], [1, 2, 3])

    def test_blank_lines_and_comments_are_skipped(self):
        plot = parse_plot("# a note\n\nreal line\n\n   \n# another\nsecond\n")
        self.assertEqual([s.text for s in plot.scenes], ["real line", "second"])

    def test_hashtags_inside_text_survive(self):
        plot = parse_plot("follow for more #coffee\n")
        self.assertEqual(plot.scenes[0].text, "follow for more #coffee")

    def test_pipe_splits_text_from_visual(self):
        plot = parse_plot("Text on screen | a cat wearing sunglasses\n")
        scene = plot.scenes[0]
        self.assertEqual(scene.text, "Text on screen")
        self.assertEqual(scene.visual, "a cat wearing sunglasses")

    def test_visual_only_line(self):
        plot = parse_plot("| just a picture\n")
        self.assertEqual(plot.scenes[0].text, "")
        self.assertEqual(plot.scenes[0].visual, "just a picture")

    def test_front_matter(self):
        plot = parse_plot(
            "---\ntitle: My Video\nstyle: neon\nseconds_per_scene: 2\n"
            "voiceover: yes\naspect: 1:1\nvibe: chaotic\n---\nline one\nline two\n"
        )
        self.assertEqual(plot.title, "My Video")
        self.assertEqual(plot.style, "neon")
        self.assertEqual(plot.aspect, "1:1")
        self.assertTrue(plot.voiceover)
        self.assertEqual(plot.extras, {"vibe": "chaotic"})
        self.assertEqual(plot.duration, 4)

    def test_per_scene_duration_override(self):
        plot = parse_plot("---\nseconds_per_scene: 3\n---\n(1.5s) quick\nnormal\n")
        self.assertEqual([s.seconds for s in plot.scenes], [1.5, 3.0])
        self.assertEqual(plot.duration, 4.5)

    def test_roles(self):
        plot = parse_plot("a\nb\nc\n")
        self.assertEqual([s.role for s in plot.scenes], ["hook", "beat", "payoff"])

    def test_single_scene_is_only_a_hook(self):
        plot = parse_plot("just one\n")
        self.assertEqual([s.role for s in plot.scenes], ["hook"])

    def test_empty_plot_rejected(self):
        with self.assertRaises(ParseError):
            parse_plot("# only comments\n\n")

    def test_unclosed_front_matter_rejected(self):
        with self.assertRaises(ParseError):
            parse_plot("---\ntitle: oops\nline\n")

    def test_bad_front_matter_values_rejected(self):
        with self.assertRaises(ParseError):
            parse_plot("---\nvoiceover: maybe\n---\nline\n")
        with self.assertRaises(ParseError):
            parse_plot("---\nseconds_per_scene: forever\n---\nline\n")
        with self.assertRaises(ParseError):
            parse_plot("---\nseconds_per_scene: 900\n---\nline\n")

    def test_json_round_trip(self):
        plot = parse_plot("---\ntitle: T\n---\none | pic\ntwo\n")
        data = json.loads(plot.to_json())
        self.assertEqual(data["scene_count"], 2)
        self.assertEqual(data["scenes"][0]["visual"], "pic")


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.plot = parse_plot(
            "---\ntitle: Coffee\nstyle: neon\nseconds_per_scene: 2\nmusic: lo-fi\n---\n"
            "Hook line | a kettle\nMiddle beat\n(5s) Payoff line | two cups\n"
        )
        self.prompt = build_prompt(self.plot)

    def test_every_line_of_text_appears_verbatim(self):
        for text in ("Hook line", "Middle beat", "Payoff line"):
            self.assertIn(text, self.prompt)

    def test_scene_order_is_preserved(self):
        positions = [self.prompt.index(t) for t in ("Hook line", "Middle beat", "Payoff line")]
        self.assertEqual(positions, sorted(positions))

    def test_metadata_reaches_the_brief(self):
        self.assertIn("Coffee", self.prompt)
        self.assertIn("neon", self.prompt)
        self.assertIn("lo-fi", self.prompt)
        self.assertIn("1080x1920", self.prompt)
        self.assertIn("9s total", self.prompt)

    def test_no_voiceover_by_default(self):
        self.assertIn("No voiceover", self.prompt)

    def test_voiceover_opt_in(self):
        prompt = build_prompt(parse_plot("---\nvoiceover: true\n---\nline\n"))
        self.assertIn("voiceover that reads", prompt)

    def test_missing_visual_is_inferred_not_left_blank(self):
        self.assertIn("Middle beat", self.prompt)
        block = self.prompt.split("Scene 2")[1]
        self.assertIn("Picture:", block)


class StoryboardTests(unittest.TestCase):
    def test_html_contains_every_scene_and_escapes_markup(self):
        plot = parse_plot("safe line\n<script>alert(1)</script> & more\n")
        html = build_storyboard(plot)
        self.assertIn("safe line", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)

    def test_aspect_ratio_follows_metadata(self):
        html = build_storyboard(parse_plot("---\naspect: 1:1\n---\nline\n"))
        self.assertIn("1 / 1", html)


if __name__ == "__main__":
    unittest.main()
