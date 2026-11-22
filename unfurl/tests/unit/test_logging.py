import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestPackageLogging(unittest.TestCase):

    def test_package_logs_go_to_stderr_not_stdout(self):
        """A log line in stdout corrupts piped output, so the package handler must use stderr.

        Run in a fresh interpreter: the handler binds its stream at import time, and the
        test runner may already have imported unfurl with its own streams in place.
        """
        code = ('import logging, unfurl; '
                'print("RESULT"); '
                'logging.getLogger("unfurl.parsers.example").error("parser blew up")')
        env = dict(os.environ, PYTHONPATH=REPO_ROOT + os.pathsep + os.environ.get('PYTHONPATH', ''))
        completed = subprocess.run(
            [sys.executable, '-c', code], capture_output=True, text=True, env=env, cwd=REPO_ROOT, timeout=120)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), 'RESULT')
        self.assertIn('parser blew up', completed.stderr)


if __name__ == '__main__':
    unittest.main()
