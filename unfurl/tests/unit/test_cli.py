from unfurl import cli
import io
import unittest
from unittest import mock


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


if __name__ == '__main__':
    unittest.main()
