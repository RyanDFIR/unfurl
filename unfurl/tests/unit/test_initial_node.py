from unfurl.core import Unfurl
from unfurl.parsers.parse_initial_node import cleaning_edge, refang
import unittest


def _unfurl(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


def _nodes_with_value(test, value):
    return [n for n in test.nodes.values() if n.value == value]


def _parent(test, node):
    return test.get_predecessor_node(node)[0]


class TestRefang(unittest.TestCase):

    def test_defanged_url_is_refanged_and_parsed(self):
        test = _unfurl('hxxps://volmira[.]site/api/ext?p=98d8049e-804f-11f1-b79f-ae3a8bb85d01')

        # The input itself is kept as it was entered
        self.assertEqual(
            'hxxps://volmira[.]site/api/ext?p=98d8049e-804f-11f1-b79f-ae3a8bb85d01',
            test.nodes[1].value)

        refanged = _nodes_with_value(
            test, 'https://volmira.site/api/ext?p=98d8049e-804f-11f1-b79f-ae3a8bb85d01')
        self.assertEqual(1, len(refanged))
        self.assertIs(cleaning_edge, refanged[0].incoming_edge_config)
        self.assertEqual(1, _parent(test, refanged[0]).node_id)

        # The refanged URL is parsed like any other
        hostnames = [n for n in test.nodes.values() if n.data_type == 'url.hostname']
        self.assertEqual(['volmira.site'], [n.value for n in hostnames])
        self.assertIn('98d8049e-804f-11f1-b79f-ae3a8bb85d01',
                      [n.value for n in test.nodes.values() if n.data_type == 'url.query.pair'])

    def test_defanged_input_logs_no_errors(self):
        """urlparse raises on brackets in a host, which parse_url used to let escape."""

        with self.assertNoLogs('unfurl.core', level='ERROR'):
            _unfurl('hxxps://volmira[.]site/api/ext')

    def test_hover_lists_each_replacement(self):
        _, hover = refang('hxxps://evil[.]example[.]com')

        self.assertIn('"<b>hxxp</b>" with "<b>http</b>"', hover)
        self.assertIn('"<b>[.]</b>" with "<b>.</b>" (2 times)', hover)

    def test_defang_conventions(self):
        cases = {
            'hxxp://evil[.]com': 'http://evil.com',
            'hxxps://evil[.]com': 'https://evil.com',
            'HXXPS://evil[.]com': 'HTTPS://evil.com',
            'hXXps://evil[.]com': 'hTTps://evil.com',
            'https[:]//evil.com': 'https://evil.com',
            'hxxps[://]evil.com': 'https://evil.com',
            'evil(.)com': 'evil.com',
            'evil[dot]com': 'evil.com',
            'evil(DOT)com': 'evil.com',
            'evil.com[/]path/x': 'evil.com/path/x',
            'hxxps://evil[.]com[/]path[/]x': 'https://evil.com/path/x',
            '1.2.3[.]4': '1.2.3.4',
            'hxxp://1.2.3[.]4[:]8080/x': 'http://1.2.3.4:8080/x',
            'user[@]evil[.]com': 'user@evil.com',
            'user[at]evil.com': 'user@evil.com',
            'user(AT)evil.com': 'user@evil.com',
        }

        for defanged, expected in cases.items():
            with self.subTest(defanged=defanged):
                self.assertEqual(expected, refang(defanged)[0])

    def test_markers_past_the_host_are_refanged_once_the_host_is(self):
        """Defanging tools commonly bracket every dot, not just the host's."""

        self.assertEqual('https://evil.com/payload.exe',
                         refang('hxxps://evil[.]com/payload[.]exe')[0])
        self.assertEqual('https://evil.com/r?u=http://other.com',
                         refang('hxxps://evil[.]com/r?u=hxxp://other[.]com')[0])

    def test_url_that_is_not_defanged_is_left_alone(self):
        """Brackets in a path or query are real content, not defanging."""

        for value in ('https://example.com/search?q=foo(.)bar',
                      'https://example.com/wiki/a[.]b',
                      'https://example.com/r?u=hxxp://evil[.]com',
                      'https://example.com/#user[at]example.com',
                      'https://example.com/?br[/]=x',
                      'https://{{.}}.example.com/',
                      'C:\\Users\\me\\Documents\\.hidden',
                      'http://[::1]:8080/',
                      'http://[2001:db8::1]/',
                      'hxxp.example.com',
                      'https://example.com/'):
            with self.subTest(value=value):
                self.assertIsNone(refang(value))
                test = _unfurl(value)
                self.assertFalse([n for n in test.nodes.values()
                                  if n.incoming_edge_config is cleaning_edge])


class TestCleaningChain(unittest.TestCase):

    def test_quoted_defanged_url_is_cleaned_in_steps(self):
        test = _unfurl('"hxxps://evil[.]com/a"')

        unquoted = _nodes_with_value(test, 'hxxps://evil[.]com/a')
        refanged = _nodes_with_value(test, 'https://evil.com/a')

        self.assertEqual(1, len(unquoted))
        self.assertEqual(1, len(refanged))
        self.assertEqual(1, _parent(test, unquoted[0]).node_id)
        self.assertIs(unquoted[0], _parent(test, refanged[0]))
        self.assertIn('evil.com', [n.value for n in test.nodes.values()
                                   if n.data_type == 'url.hostname'])

    def test_defanged_url_with_spaces_is_cleaned(self):
        test = _unfurl('hxxps://evil [.] com/a')

        refanged = _nodes_with_value(test, 'https://evil.com/a')
        self.assertEqual(1, len(refanged))
        self.assertEqual('hxxps://evil[.]com/a', _parent(test, refanged[0]).value)

    def test_steps_build_on_each_other_without_duplicate_branches(self):
        """Quotes and whitespace used to each be removed from the input separately, so
        neither result had both removed."""

        test = _unfurl('"a b"')

        self.assertEqual(1, len(_nodes_with_value(test, 'ab')))
        self.assertFalse(_nodes_with_value(test, 'a b'))


if __name__ == '__main__':
    unittest.main()
