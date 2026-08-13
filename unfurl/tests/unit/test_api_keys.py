import os
import unittest
from unittest.mock import patch

from unfurl.core import Unfurl, config_paths

VT_ENV = 'UNFURL_VIRUSTOTAL_API_KEY'


class TestGetApiKey(unittest.TestCase):
    """Tests for Unfurl.get_api_key(), which resolves an API key from the config files
    and then from the environment.

    The tracked unfurl.ini template lists every key with an empty value, so "set but
    empty" has to resolve the same way as "not present at all" — otherwise the
    environment fallback would never fire for anyone using the template.
    """

    @classmethod
    def setUpClass(cls):
        # get_api_key() only reads self.api_keys and os.environ, so a single instance can
        # be shared across these tests; constructing an Unfurl is comparatively slow.
        cls.unfurl = Unfurl()

    def setUp(self):
        # Don't inherit whatever the developer's own config happens to hold.
        self.unfurl.api_keys = {}

    def test_key_from_config(self):
        self.unfurl.api_keys = {'virustotal': 'key_from_config'}
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'key_from_config')

    def test_config_value_beats_environment(self):
        self.unfurl.api_keys = {'virustotal': 'key_from_config'}
        with patch.dict(os.environ, {VT_ENV: 'key_from_env'}):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'key_from_config')

    def test_key_from_environment_when_absent_from_config(self):
        with patch.dict(os.environ, {VT_ENV: 'key_from_env'}):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'key_from_env')

    def test_empty_config_value_falls_back_to_environment(self):
        """An empty value is what the unfurl.ini template ships; it must not mask the env var."""
        self.unfurl.api_keys = {'virustotal': ''}
        with patch.dict(os.environ, {VT_ENV: 'key_from_env'}):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'key_from_env')

    def test_env_var_name_is_namespaced_and_uppercased(self):
        self.assertEqual(Unfurl.api_key_env_var('virustotal'), 'UNFURL_VIRUSTOTAL_API_KEY')
        self.assertEqual(Unfurl.api_key_env_var('google_kg'), 'UNFURL_GOOGLE_KG_API_KEY')

    def test_empty_config_value_with_no_environment_is_none(self):
        self.unfurl.api_keys = {'virustotal': ''}
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.unfurl.get_api_key('virustotal'))

    def test_unset_key_is_none(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.unfurl.get_api_key('virustotal'))

    def test_empty_environment_value_is_none(self):
        """Callers check truthiness, so an empty env var must not read as a configured key."""
        with patch.dict(os.environ, {VT_ENV: ''}):
            self.assertIsNone(self.unfurl.get_api_key('virustotal'))

    def test_keys_do_not_leak_between_services(self):
        self.unfurl.api_keys = {'virustotal': 'vt_key'}
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'vt_key')
            self.assertIsNone(self.unfurl.get_api_key('bitly'))


class TestLegacyEnvironmentVariables(unittest.TestCase):
    """Older versions read a bare lowercase env var (e.g. "virustotal").

    That interface has to keep working: pip installs ship no unfurl.ini, so `api_keys`
    is empty for those users and the bare env var was the only way to supply a key that
    actually took effect.
    """

    @classmethod
    def setUpClass(cls):
        cls.unfurl = Unfurl()

    def setUp(self):
        self.unfurl.api_keys = {}

    def test_legacy_bare_name_is_still_honored(self):
        with patch.dict(os.environ, {'virustotal': 'legacy_key'}, clear=True):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'legacy_key')

    def test_legacy_bare_name_warns(self):
        with patch.dict(os.environ, {'virustotal': 'legacy_key'}, clear=True):
            with self.assertLogs('unfurl.core', level='WARNING') as logged:
                self.unfurl.get_api_key('virustotal')
        self.assertIn(VT_ENV, ''.join(logged.output))

    def test_namespaced_name_beats_legacy(self):
        with patch.dict(os.environ, {VT_ENV: 'new_key', 'virustotal': 'legacy_key'}, clear=True):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'new_key')

    def test_namespaced_name_does_not_warn(self):
        with patch.dict(os.environ, {VT_ENV: 'new_key'}, clear=True):
            with self.assertNoLogs('unfurl.core', level='WARNING'):
                self.unfurl.get_api_key('virustotal')

    def test_config_beats_legacy(self):
        self.unfurl.api_keys = {'virustotal': 'key_from_config'}
        with patch.dict(os.environ, {'virustotal': 'legacy_key'}, clear=True):
            self.assertEqual(self.unfurl.get_api_key('virustotal'), 'key_from_config')

    def test_empty_legacy_value_is_none(self):
        with patch.dict(os.environ, {'virustotal': ''}, clear=True):
            self.assertIsNone(self.unfurl.get_api_key('virustotal'))


class TestConfigPaths(unittest.TestCase):

    def test_local_config_is_read_after_every_template(self):
        """unfurl.local.ini must always win over unfurl.ini, in any search directory.

        configparser applies files in order, so if a template were read after a local
        file, its empty API keys would clobber real ones.
        """
        paths = [os.path.basename(p) for p in config_paths()]
        last_template = max(i for i, name in enumerate(paths) if name == 'unfurl.ini')
        first_local = min(i for i, name in enumerate(paths) if name == 'unfurl.local.ini')
        self.assertLess(
            last_template, first_local,
            'a template config must never be read after a local one')


if __name__ == '__main__':
    unittest.main()
