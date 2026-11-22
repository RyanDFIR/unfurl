from unfurl import cli
import io
import json
import os
import tempfile
import unittest
from unittest import mock


def run_cli(*args):
    """Run the CLI with these arguments; return what it printed to stdout."""
    stdout = io.StringIO()
    with mock.patch.dict('os.environ', {'PYTHONIOENCODING': 'utf-8'}), \
            mock.patch.object(cli.sys, 'argv', ['unfurl', *args]), \
            mock.patch.object(cli.sys, 'stdout', stdout):
        cli.command_line_interface()
    return stdout.getvalue()


def walk_tree(node):
    """Yield every node in a nested JSON tree, root first."""
    yield node
    for child in node['children']:
        yield from walk_tree(child)


class FakeStream:
    """Minimal stand-in for a text stream that records reconfigure() calls."""

    def __init__(self, encoding='cp1252', fails_on_encoding=False):
        self.encoding = encoding
        self.errors = 'strict'
        self.fails_on_encoding = fails_on_encoding
        self.calls = []

    def reconfigure(self, encoding=None, errors=None):
        self.calls.append((encoding, errors))
        if encoding is not None:
            if self.fails_on_encoding:
                raise ValueError('cannot change encoding')
            self.encoding = encoding
        if errors is not None:
            self.errors = errors


class TestConfigureOutputEncoding(unittest.TestCase):

    def test_switches_console_streams_to_utf8(self):
        """A cp1252 console can't encode the tree's box-drawing characters."""

        out, err = FakeStream(), FakeStream()
        with mock.patch.dict('os.environ', {}, clear=True), \
                mock.patch.object(cli.sys, 'stdout', out), \
                mock.patch.object(cli.sys, 'stderr', err):
            cli.configure_output_encoding()

        self.assertEqual('utf-8', out.encoding)
        self.assertEqual('utf-8', err.encoding)

    def test_respects_explicit_pythonioencoding(self):
        """If the user set PYTHONIOENCODING, that choice wins."""

        out = FakeStream()
        with mock.patch.dict('os.environ', {'PYTHONIOENCODING': 'cp1252'}), \
                mock.patch.object(cli.sys, 'stdout', out):
            cli.configure_output_encoding()

        self.assertEqual([], out.calls)
        self.assertEqual('cp1252', out.encoding)

    def test_falls_back_to_replacing_unencodable_characters(self):
        """A stream that won't change encoding should at least stop raising."""

        out = FakeStream(fails_on_encoding=True)
        with mock.patch.dict('os.environ', {}, clear=True), \
                mock.patch.object(cli.sys, 'stdout', out):
            cli.configure_output_encoding()

        self.assertEqual('replace', out.errors)

    def test_tolerates_stream_without_reconfigure(self):
        """sys.stdout may have been replaced by something that isn't a TextIOWrapper."""

        out = io.StringIO()
        with mock.patch.dict('os.environ', {}, clear=True), \
                mock.patch.object(cli.sys, 'stdout', out), \
                mock.patch.object(cli.sys, 'stderr', out):
            cli.configure_output_encoding()  # must not raise


class TestCommandLineInterface(unittest.TestCase):

    def test_tree_output_survives_a_cp1252_console(self):
        """The end-to-end regression: unfurl a URL with stdout set to cp1252.

        Before configure_output_encoding(), printing the tree raised
        UnicodeEncodeError on the box-drawing characters.
        """

        buffer = io.TextIOWrapper(
            io.BytesIO(), encoding='cp1252', newline='', write_through=True)

        argv = ['unfurl', 'https://example.com/path?a=1']
        with mock.patch.dict('os.environ', {}, clear=True), \
                mock.patch.object(cli.sys, 'argv', argv), \
                mock.patch.object(cli.sys, 'stdout', buffer):
            cli.command_line_interface()

        buffer.seek(0)
        output = buffer.buffer.getvalue().decode('utf-8')
        self.assertIn('Scheme: https', output)
        self.assertIn('├', output)  # the tree's box-drawing characters


class TestJsonOutput(unittest.TestCase):

    url = 'https://example.com/path?a=1'

    def test_json_is_parseable_and_nested(self):
        record = json.loads(run_cli('-t', 'json', self.url))

        self.assertEqual(self.url, record['input'])
        self.assertIn('unfurl_version', record)

        root = record['tree']
        self.assertEqual(self.url, root['value'])
        self.assertIsNone(root['edge'])

        scheme = next(n for n in root['children'] if n['data_type'] == 'url.scheme')
        self.assertEqual('https', scheme['value'])
        self.assertEqual('URL Parsing Functions', scheme['edge']['title'])

        query_pair = next(n for n in walk_tree(root) if n['data_type'] == 'url.query.pair')
        self.assertEqual('a', query_pair['key'])

    def test_json_nodes_have_a_stable_shape_without_markup(self):
        root = json.loads(run_cli('-t', 'json', self.url))['tree']
        for node in walk_tree(root):
            self.assertIsInstance(node['children'], list)
            self.assertNotIn('extra_options', node)
            self.assertNotIn('<', node['description'] or '')

    def test_json_flat_links_nodes_by_parent_id(self):
        nodes = json.loads(run_cli('-t', 'json-flat', self.url))['nodes']

        self.assertIsNone(nodes[0]['parent_id'])
        self.assertEqual(self.url, nodes[0]['value'])

        seen = set()
        for node in nodes:
            if node['parent_id'] is not None:
                self.assertIn(node['parent_id'], seen)  # parents come first
            seen.add(node['id'])

        scheme = next(n for n in nodes if n['data_type'] == 'url.scheme')
        self.assertEqual(nodes[0]['id'], scheme['parent_id'])

    def test_lineage_names_each_step_by_key_or_data_type(self):
        url = 'https://example.com/?t=1700000000'
        root = json.loads(run_cli('-t', 'json', url))['tree']

        self.assertEqual(['url'], root['lineage'])  # no key, so the data_type

        timestamp = next(
            n for n in walk_tree(root) if n['data_type'] == 'timestamp.epoch-seconds')
        self.assertEqual('url', timestamp['lineage'][0])
        self.assertEqual(['t', 'timestamp.epoch-seconds'], timestamp['lineage'][-2:])

    def test_lineage_is_the_same_in_nested_and_flat_output(self):
        url = 'https://example.com/?t=1700000000'
        nested = json.loads(run_cli('-t', 'json', url))['tree']
        flat = json.loads(run_cli('-t', 'json-flat', url))['nodes']

        self.assertEqual(
            {n['id']: n['lineage'] for n in walk_tree(nested)},
            {n['id']: n['lineage'] for n in flat})

    def test_file_input_gives_one_json_line_per_input(self):
        second_url = 'https://example.org/other'
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'inputs.txt')
            with open(input_path, 'w') as f:
                f.write(f'{self.url}\n{second_url}\n')
            lines = run_cli('-t', 'json', input_path).splitlines()

        self.assertEqual(
            [self.url, second_url], [json.loads(line)['input'] for line in lines])

    def test_output_file_is_json_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'out.jsonl')
            run_cli('-t', 'json-flat', '-o', output_path, self.url)
            with open(output_path, encoding='utf-8') as f:
                lines = f.read().splitlines()

        self.assertEqual(self.url, json.loads(lines[0])['input'])

    def test_filter_on_nested_keeps_matches_and_their_ancestors(self):
        url = 'https://example.com/?t=1700000000'
        root = json.loads(run_cli('-t', 'json', '-f', '2023-11-14', url))['tree']

        nodes = list(walk_tree(root))
        matches = [n for n in nodes if n['matched']]
        self.assertEqual(['timestamp.epoch-seconds'], [n['data_type'] for n in matches])

        # What's left is the single chain from the input down to the match.
        self.assertEqual(matches[0]['lineage'], [n['lineage'][-1] for n in nodes])
        self.assertFalse(root['matched'])

    def test_filter_on_nested_with_no_match_gives_no_tree(self):
        record = json.loads(run_cli('-t', 'json', '-f', 'no such label', self.url))
        self.assertIsNone(record['tree'])

    def test_filter_on_flat_keeps_only_matches(self):
        url = 'https://example.com/?t=1700000000'
        nodes = json.loads(run_cli('-t', 'json-flat', '-f', '2023-11-14', url))['nodes']

        self.assertEqual(['timestamp.epoch-seconds'], [n['data_type'] for n in nodes])
        self.assertEqual(['t', 'timestamp.epoch-seconds'], nodes[0]['lineage'][-2:])

    def test_invalid_filter_regex_is_a_usage_error(self):
        with mock.patch.object(cli.sys, 'stderr', io.StringIO()), \
                self.assertRaises(SystemExit):
            run_cli('-t', 'json', '-f', '(unclosed', self.url)


if __name__ == '__main__':
    unittest.main()
