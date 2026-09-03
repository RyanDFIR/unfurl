from unfurl.utils import wrap_hover_text, wrap_width, wrap_slack
import re
import unittest


def visible(text):
    """The text with markup removed, which is what the width is meant to measure."""
    return re.sub(r'<[^>]+>', '', text)


def lines(wrapped):
    return wrapped.split('<br>')


class TestHoverWrapping(unittest.TestCase):

    def test_empty_and_non_string_input(self):
        for value in (None, '', 0, [], {}):
            with self.subTest(value=value):
                self.assertIsNone(wrap_hover_text(value))

    def test_short_text_is_left_alone(self):
        short = 'Search Query used in Bing'
        self.assertEqual(short, wrap_hover_text(short))

    def test_slightly_long_text_stays_on_one_line(self):
        """One slightly long line beats a long line plus a short orphan."""

        almost = 'x' * (wrap_width + wrap_slack - 1)
        self.assertEqual(almost, wrap_hover_text(almost))

    def test_long_text_is_wrapped(self):
        text = ('Indicates the user arrived at Bing image results by having manually typed a '
                'search term into the main Bing search engine then scrolled down the page.')

        wrapped = lines(wrap_hover_text(text))

        self.assertGreater(len(wrapped), 1)
        self.assertLessEqual(max(len(line) for line in wrapped), wrap_width)


class TestHoverWrappingHonorsAuthorBreaks(unittest.TestCase):
    """A <br> in the source is a decision about where a line ends, not an accident."""

    def test_hard_breaks_are_kept_where_they_are(self):
        text = ('The index of the first result shown on the page.<br>'
                'Results per page varies by Bing vertical.')

        self.assertEqual(
            ['The index of the first result shown on the page.',
             'Results per page varies by Bing vertical.'],
            lines(wrap_hover_text(text)))

    def test_text_is_never_wrapped_across_a_hard_break(self):
        """Two short runs stay two runs; they must not be reflowed into one line."""

        text = 'Short first line.<br>Short second line.'
        self.assertEqual(text, wrap_hover_text(text))

    def test_each_run_is_wrapped_on_its_own(self):
        """A long run next to a hard break still gets wrapped.

        This is the case the old implementation could not handle: it returned any hover
        containing a <br> untouched, so a long explanation appended after a separator was
        never wrapped at all.
        """

        preamble = 'The "form" parameter records how the user navigated to this page.'
        explanation = ('Indicates the user arrived at Bing image results by having manually typed '
                       'a search term into the main Bing search engine then scrolled down the '
                       'results page and selected a thumbnail image.')

        wrapped = lines(wrap_hover_text(f'{preamble}<br><br>{explanation}'))

        self.assertEqual(preamble, wrapped[0])
        self.assertEqual('', wrapped[1], 'the blank paragraph gap should survive')
        self.assertGreater(len(wrapped), 3, 'the explanation should have been wrapped')
        self.assertLessEqual(max(len(line) for line in wrapped[2:]), wrap_width)

    def test_paragraph_gap_is_preserved(self):
        self.assertEqual(['a', '', 'b'], lines(wrap_hover_text('a<br><br>b')))


class TestHoverWrappingMeasuresVisibleWidth(unittest.TestCase):
    """Markup is held aside before wrapping, so lines are measured by what renders."""

    def test_inline_tags_do_not_shorten_lines(self):
        """<b>q</b> is 12 characters of markup for one the reader sees."""

        text = ('Partial search terms entered by the user; auto-complete or suggestions may '
                'have been used to reach the actual terms (in <b>q</b>) shown here.')

        wrapped = lines(wrap_hover_text(text))

        # Measured on rendered text, every line is within the width; measured on raw
        # markup the <b> line would appear over it and get broken early.
        self.assertLessEqual(max(len(visible(line)) for line in wrapped), wrap_width)
        self.assertIn('<b>q</b>', wrap_hover_text(text))

    def test_a_break_never_lands_inside_a_tag(self):
        text = ('See the reference for this parameter at '
                '<a href="https://github.com/obsidianforensics/unfurl/issues/56" target="_blank">'
                'issue 56</a> for the full discussion of how this value was worked out.')

        wrapped = lines(wrap_hover_text(text))

        for line in wrapped:
            with self.subTest(line=line):
                self.assertEqual(line.count('<'), line.count('>'), 'a tag was split')

    def test_an_anchor_is_held_whole(self):
        anchor = ('<a href="https://github.com/obsidianforensics/unfurl/issues/56" '
                  'target="_blank">issue 56</a>')
        text = f'See the reference for this parameter at {anchor} for the full discussion here.'

        self.assertIn(anchor, wrap_hover_text(text))

    def test_a_long_href_does_not_wrap_the_text_short(self):
        """The href's characters never render, so they must not consume the line budget."""

        anchor = ('<a href="https://example.com/' + 'x' * 200 + '" target="_blank">ref</a>')
        text = f'Short note with a reference {anchor} and a few more words after it.'

        # Held aside, the visible text is short enough to stay on one line.
        self.assertEqual(text, wrap_hover_text(text))


class TestHoverWrappingWordBreaks(unittest.TestCase):

    def test_hyphenated_words_are_not_split(self):
        """textwrap breaks on hyphens by default, which mangles words like "full-size"."""

        text = ('The user opened the full-size image within the browser after clicking a '
                'thumbnail on the results page for that search term.')

        wrapped = wrap_hover_text(text)

        self.assertNotIn('full-<br>size', wrapped)
        self.assertIn('full-size', wrapped)


if __name__ == '__main__':
    unittest.main()
