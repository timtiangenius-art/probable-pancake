import json
import unittest
from pathlib import Path

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


class SuppliedImageTests(unittest.TestCase):
    def test_image_path_is_read_as_a_picture_not_a_description(self):
        plot = parse_plot("My text | shots/01.jpg\n")
        scene = plot.scenes[0]
        self.assertEqual(scene.image, "shots/01.jpg")
        self.assertEqual(scene.image_kind, "local")
        self.assertTrue(scene.image_is_local)
        self.assertEqual(scene.visual, "")

    def test_remote_and_data_urls(self):
        plot = parse_plot(
            "a | https://cdn.example.com/x.jpg\n"
            "b | http://example.com/y.png\n"
            "c | data:image/png;base64,AAAA\n"
        )
        self.assertEqual([s.image_kind for s in plot.scenes], ["url", "url", "data"])
        self.assertFalse(any(s.image_is_local for s in plot.scenes))

    def test_url_without_an_image_extension_still_counts(self):
        plot = parse_plot("a | https://example.com/photo?id=7\n")
        self.assertEqual(plot.scenes[0].image_kind, "url")

    def test_picture_and_direction_in_either_order(self):
        first = parse_plot("a | shots/01.jpg | slow push-in\n").scenes[0]
        second = parse_plot("a | slow push-in | shots/01.jpg\n").scenes[0]
        for scene in (first, second):
            self.assertEqual(scene.image, "shots/01.jpg")
            self.assertEqual(scene.visual, "slow push-in")

    def test_prose_mentioning_a_filename_midway_stays_prose(self):
        plot = parse_plot("a | the shots/01.jpg file is the wrong one, use a kettle\n")
        self.assertEqual(plot.scenes[0].image, "")
        self.assertIn("kettle", plot.scenes[0].visual)

    def test_img_prefix_forces_an_extensionless_name(self):
        plot = parse_plot("a | img:IMG_2049\n")
        self.assertEqual(plot.scenes[0].image, "IMG_2049")
        self.assertEqual(plot.scenes[0].image_kind, "local")

    def test_two_pictures_on_one_line_is_an_error(self):
        with self.assertRaises(ParseError):
            parse_plot("a | one.jpg | two.jpg\n")

    def test_picture_only_scene_needs_no_text(self):
        plot = parse_plot("| shots/01.jpg\n")
        self.assertEqual(plot.scenes[0].text, "")
        self.assertEqual(plot.scenes[0].image, "shots/01.jpg")

    def test_scene_counts(self):
        plot = parse_plot("a | one.jpg\nb | words only\nc | https://e.com/z.png\n")
        self.assertEqual(len(plot.with_images), 2)
        self.assertEqual(len(plot.local_images), 1)

    def test_asset_base_rewrites_local_paths_only(self):
        plot = parse_plot("a | shots/01.jpg\nb | https://cdn.example.com/keep.png\n")
        plot.apply_asset_base("https://cdn.example.com/run7/")
        self.assertEqual(plot.scenes[0].image, "https://cdn.example.com/run7/shots/01.jpg")
        self.assertEqual(plot.scenes[0].image_kind, "url")
        self.assertEqual(plot.scenes[1].image, "https://cdn.example.com/keep.png")
        self.assertEqual(plot.local_images, [])

    def test_asset_map_rewrites_named_paths(self):
        plot = parse_plot("a | shots/01.jpg\nb | shots/02.jpg\n")
        plot.apply_asset_map({"shots/01.jpg": "https://cdn.example.com/a.jpg"})
        self.assertEqual(plot.scenes[0].image, "https://cdn.example.com/a.jpg")
        self.assertEqual(plot.scenes[1].image, "shots/02.jpg")


class SuppliedImagePromptTests(unittest.TestCase):
    def test_supplied_url_is_pinned_and_protected(self):
        prompt = build_prompt(parse_plot("Hook | https://cdn.example.com/a.jpg\n"))
        self.assertIn("https://cdn.example.com/a.jpg", prompt)
        self.assertIn("exactly as provided", prompt)
        self.assertIn("Do not regenerate", prompt)

    def test_unhosted_local_file_is_flagged_loudly(self):
        prompt = build_prompt(parse_plot("Hook | shots/01.jpg\n"))
        self.assertIn("UNHOSTED LOCAL FILE", prompt)
        self.assertIn("shots/01.jpg", prompt)

    def test_scene_without_a_picture_still_gets_direction(self):
        prompt = build_prompt(parse_plot("Hook | https://e.com/a.jpg\nPlain line\n"))
        block = prompt.split("Scene 2")[1]
        self.assertIn("Picture:", block)
        self.assertNotIn("exactly as provided", block)

    def test_supplied_count_reaches_the_rules(self):
        prompt = build_prompt(parse_plot("a | https://e.com/1.jpg\nb\nc | https://e.com/2.jpg\n"))
        self.assertIn("2 of the 3 scenes come with the author's own picture", prompt)

    def test_treatment_note_rides_along_with_the_image(self):
        prompt = build_prompt(parse_plot("a | https://e.com/1.jpg | slow push-in\n"))
        self.assertIn("Treatment for that image: slow push-in", prompt)


class SuppliedImageStoryboardTests(unittest.TestCase):
    def test_remote_image_is_referenced(self):
        html = build_storyboard(parse_plot("a | https://cdn.example.com/x.jpg\n"))
        self.assertIn('src="https://cdn.example.com/x.jpg"', html)
        self.assertIn('class="frame has-photo"', html)

    def test_missing_local_file_is_called_out(self):
        html = build_storyboard(parse_plot("a | nowhere/nothing.jpg\n"))
        self.assertIn("missing file", html)
        self.assertNotIn('class="frame has-photo"', html)
        self.assertNotIn("<img", html)


class HostingTests(unittest.TestCase):
    def test_parses_every_github_remote_shape(self):
        from tiktok_plot.hosting import parse_github_remote

        for url in (
            "git@github.com:owner/repo.git",
            "https://github.com/owner/repo.git",
            "https://github.com/owner/repo",
            "https://token@github.com/owner/repo.git",
            "https://github.com/owner/repo/",
        ):
            self.assertEqual(parse_github_remote(url), ("owner", "repo"), url)

    def test_rejects_non_github_remotes(self):
        from tiktok_plot.hosting import HostingError, parse_github_remote

        with self.assertRaises(HostingError):
            parse_github_remote("git@gitlab.com:owner/repo.git")

    def test_non_github_asset_base_passes_through(self):
        from tiktok_plot.hosting import resolve_asset_base

        base = "https://cdn.example.com/shots"
        self.assertEqual(resolve_asset_base(base, Path(".")), base)


class FrontMatterPositionTests(unittest.TestCase):
    def test_comments_may_precede_the_front_matter(self):
        plot = parse_plot(
            "# how to build this\n# second note\n\n---\ntitle: T\n---\nline one\nline two\n"
        )
        self.assertEqual(plot.title, "T")
        self.assertEqual([s.text for s in plot.scenes], ["line one", "line two"])

    def test_a_plot_with_no_front_matter_still_starts_at_line_one(self):
        plot = parse_plot("# note\nline one\n")
        self.assertEqual([s.text for s in plot.scenes], ["line one"])
