import configparser
import os
import unittest
from unittest.mock import patch

from unfurl import core
from unfurl.core import REMOTE_LOOKUPS_ENV_VAR, Unfurl, resolve_remote_lookups


def make_config(remote_lookups=None):
    """A config object with [UNFURL_APP] remote_lookups set to `remote_lookups`."""
    config = configparser.ConfigParser()
    if remote_lookups is not None:
        config['UNFURL_APP'] = {'remote_lookups': remote_lookups}
    return config


class TestResolveRemoteLookups(unittest.TestCase):
    """Precedence is: explicit request (CLI -l) > UNFURL_REMOTE_LOOKUPS > config files.

    Remote lookups send data from the input to third parties, so every path defaults to
    disabled and anything uninterpretable fails closed.
    """

    def setUp(self):
        # The "enabled via environment" notice is warn-once per process.
        core._warned_about_env_remote_lookups = False

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(resolve_remote_lookups(config=make_config()))

    def test_config_enables(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(resolve_remote_lookups(config=make_config('true')))

    def test_environment_beats_config(self):
        """A container can enable lookups without editing the mounted unfurl.ini."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertTrue(resolve_remote_lookups(config=make_config('false')))

    def test_environment_can_also_disable(self):
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'false'}):
            self.assertFalse(resolve_remote_lookups(config=make_config('true')))

    def test_explicit_request_beats_environment(self):
        """An explicit choice is per-run, so it wins over environment and config."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'false'}):
            self.assertTrue(resolve_remote_lookups(explicit=True, config=make_config('false')))

    def test_explicit_false_beats_environment_and_config(self):
        """False must mean "off", not "unspecified".

        This tested `if explicit:` originally, so False fell through to the environment
        and config and `Unfurl(remote_lookups=False)` could not turn lookups off. On a
        machine with lookups enabled in unfurl.ini that silently made real network
        requests -- including from tests that had asked for them to be off.
        """
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertFalse(resolve_remote_lookups(explicit=False, config=make_config('true')))

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(resolve_remote_lookups(explicit=False, config=make_config('true')))

    def test_none_defers_to_environment_and_config(self):
        """None is how a caller says "not specified"; it must not force lookups off."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertTrue(resolve_remote_lookups(explicit=None, config=make_config('false')))

        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(resolve_remote_lookups(explicit=None, config=make_config('true')))

    def test_resolution_is_idempotent(self):
        """Feeding a resolved answer back in must return that same answer.

        app.py resolves once in web_app() and the resolved boolean is passed down through
        run() into Unfurl, where it is resolved again.
        """
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            once = resolve_remote_lookups(config=make_config())
            self.assertEqual(once, resolve_remote_lookups(explicit=once, config=make_config()))

        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'false'}):
            once = resolve_remote_lookups(config=make_config())
            self.assertEqual(once, resolve_remote_lookups(explicit=once, config=make_config()))

    def test_unset_environment_defers_to_config(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(resolve_remote_lookups(config=make_config('yes')))

    def test_empty_environment_defers_to_config(self):
        """Empty means "not configured", not "disabled"."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: ''}):
            self.assertTrue(resolve_remote_lookups(config=make_config('true')))

    def test_boolean_vocabulary_matches_the_config_file(self):
        for raw in ('1', 'yes', 'true', 'on', 'TRUE', ' True '):
            with self.subTest(raw=raw), patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: raw}):
                self.assertTrue(resolve_remote_lookups(config=make_config()))

        for raw in ('0', 'no', 'false', 'off', 'FALSE'):
            with self.subTest(raw=raw), patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: raw}):
                self.assertFalse(resolve_remote_lookups(config=make_config('true')))

    def test_uninterpretable_environment_value_fails_closed(self):
        """Must not fall through to a config file that would enable lookups."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'maybe'}):
            with self.assertLogs('unfurl.core', level='WARNING'):
                self.assertFalse(resolve_remote_lookups(config=make_config('true')))

    def test_uninterpretable_config_value_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(resolve_remote_lookups(config=make_config('maybe')))

    def test_enabling_via_environment_is_announced(self):
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            with self.assertLogs('unfurl.core', level='WARNING') as logged:
                resolve_remote_lookups(config=make_config())
        self.assertIn(REMOTE_LOOKUPS_ENV_VAR, ''.join(logged.output))

    def test_enabling_via_config_is_not_announced(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertNoLogs('unfurl.core', level='WARNING'):
                resolve_remote_lookups(config=make_config('true'))


class TestUnfurlHonorsEnvironment(unittest.TestCase):
    """The resolution has to actually reach a constructed Unfurl, not just the helper."""

    def setUp(self):
        core._warned_about_env_remote_lookups = False

    def test_environment_enables_lookups_on_a_new_instance(self):
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertTrue(Unfurl().remote_lookups)

    def test_environment_disables_lookups_on_a_new_instance(self):
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'false'}):
            self.assertFalse(Unfurl().remote_lookups)

    def test_explicit_request_still_wins(self):
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'false'}):
            self.assertTrue(Unfurl(remote_lookups=True).remote_lookups)

    def test_explicit_false_disables_lookups_on_a_new_instance(self):
        """Unfurl(remote_lookups=False) has to actually mean offline.

        Tests rely on this to stay off the network, and an analyst relies on it to keep
        evidence from being sent to third parties.
        """
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertFalse(Unfurl(remote_lookups=False).remote_lookups)

    def test_default_construction_defers_to_environment(self):
        """Unfurl() must keep honoring the environment, not default to off."""
        with patch.dict(os.environ, {REMOTE_LOOKUPS_ENV_VAR: 'true'}):
            self.assertTrue(Unfurl().remote_lookups)


class TestRunHonorsRemoteLookups(unittest.TestCase):
    """core.run() is the public entry point the web app and library callers use.

    Its default changed from False to None so that "not specified" stays distinguishable
    from "off" -- with a False default, fixing the resolver would have made run() ignore
    UNFURL_REMOTE_LOOKUPS and unfurl.ini entirely.
    """

    def setUp(self):
        core._warned_about_env_remote_lookups = False

    def test_default_is_none_so_the_environment_still_applies(self):
        import inspect
        default = inspect.signature(core.run).parameters['remote_lookups'].default
        self.assertIsNone(default, 'a False default would override env/config')


if __name__ == '__main__':
    unittest.main()
