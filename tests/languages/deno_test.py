"""Tests for the Deno language implementation in pre-commit."""

from __future__ import annotations

import os
import unittest
from unittest import mock

import pre_commit.constants as C
from pre_commit.languages import deno
from pre_commit.prefix import Prefix


class TestGetDefaultVersion(unittest.TestCase):
    """Tests for get_default_version function."""

    def test_returns_system_when_deno_exists(self) -> None:
        """Should return 'system' when deno binary exists."""
        with mock.patch.object(deno.lang_base, 'exe_exists', return_value=True):
            result = deno.get_default_version()
            self.assertEqual(result, 'system')

    def test_returns_default_when_deno_not_installed(self) -> None:
        """Should return C.DEFAULT when deno binary does not exist."""
        with mock.patch.object(deno.lang_base, 'exe_exists', return_value=False):
            deno.get_default_version.cache_clear()
            result = deno.get_default_version()
            self.assertEqual(result, C.DEFAULT)

    def test_default_version_cached(self) -> None:
        """Should cache the default version result."""
        with mock.patch.object(deno.lang_base, 'exe_exists', return_value=False) as mock_exe:
            deno.get_default_version.cache_clear()
            deno.get_default_version()
            deno.get_default_version()
            # Should only call exe_exists once due to caching
            self.assertEqual(mock_exe.call_count, 1)


class TestGetEnvPatch(unittest.TestCase):
    """Tests for get_env_patch function."""

    def test_returns_path_patch(self) -> None:
        """Should return a PATCH that adds bin directory to PATH."""
        venv = '/path/to/env'
        result = deno.get_env_patch(venv)

        # Check that PATH is set correctly
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'PATH')
        self.assertIn(venv, result[0][1])

    def test_bin_path_includes_separator(self) -> None:
        """Should include the bin subdirectory in the path."""
        venv = '/path/to/env'
        bin_subdir = os.path.join(venv, 'bin')
        result = deno.get_env_patch(venv)

        # The PATH entry should include bin subdirectory
        path_entry = result[0][1]
        self.assertIn(bin_subdir, path_entry)


class TestInstallEnvironment(unittest.TestCase):
    """Tests for install_environment function."""

    def test_system_version_no_op(self) -> None:
        """System version should just verify deno exists and create bin dir."""
        prefix = mock.MagicMock()
        prefix.path.return_value = '/tmp/test_env'

        with mock.patch.object(deno, 'health_check') as mock_health:
            with mock.patch('os.makedirs'):
                deno.install_environment(prefix, 'system', [])

        mock_health.assert_called_once()

    def test_version_specific_installs_via_binary_downloader(self) -> None:
        """Specific version should download binary via _install_deno_binary."""
        prefix = mock.MagicMock()
        prefix.path.return_value = '/tmp/test_env'

        with mock.patch.object(deno, '_install_deno_binary') as mock_install:
            with mock.patch.object(deno, 'health_check') as mock_health:
                deno.install_environment(prefix, '1.40.0', [])

        mock_install.assert_called_once()
        mock_health.assert_called_once()

    def test_rejects_additional_dependencies(self) -> None:
        """Should reject additional_dependencies like other simple languages."""
        prefix = mock.MagicMock()

        with self.assertRaises(AssertionError) as ctx:
            deno.install_environment(prefix, '1.0.0', ['some-dep'])

        self.assertIn('additional_dependencies', str(ctx.exception))


class TestResolveDenoVersion(unittest.TestCase):
    """Tests for version resolution."""

    def test_default_returns_latest(self) -> None:
        """DEFAULT version should map to 'latest' for download URL."""
        result = deno._resolve_deno_version(C.DEFAULT)
        self.assertEqual(result, 'latest')

    def test_specific_version_preserved(self) -> None:
        """Specific version strings should be preserved."""
        result = deno._resolve_deno_version('1.40.0')
        self.assertEqual(result, '1.40.0')

    def test_system_version_preserved(self) -> None:
        """System version should be preserved (not resolved)."""
        result = deno._resolve_deno_version('system')
        self.assertEqual(result, 'system')


class TestGetDenoUrl(unittest.TestCase):
    """Tests for download URL generation."""

    def test_returns_windows_url(self) -> None:
        """Should return Windows zip URL."""
        url = deno._get_deno_url('1.40.0', os_name='windows', arch='x86_64')
        self.assertIn('windows', url)
        self.assertIn('.zip', url)
        self.assertIn('1.40.0', url)

    def test_returns_darwin_url(self) -> None:
        """Should return macOS zip URL."""
        url = deno._get_deno_url('1.40.0', os_name='darwin', arch='x86_64')
        self.assertIn('darwin', url)
        self.assertIn('.zip', url)
        self.assertIn('1.40.0', url)

    def test_returns_linux_url(self) -> None:
        """Should return Linux zip URL."""
        url = deno._get_deno_url('1.40.0', os_name='linux', arch='x86_64')
        self.assertIn('linux', url)
        self.assertIn('.zip', url)
        self.assertIn('1.40.0', url)

    def test_returns_aarch64_url(self) -> None:
        """Should return ARM64 URL when arch is aarch64."""
        url = deno._get_deno_url('1.40.0', os_name='linux', arch='aarch64')
        self.assertIn('aarch64', url)

    def test_uses_x86_64_for_amd64(self) -> None:
        """Should map amd64 to x86_64 for compatibility."""
        url = deno._get_deno_url('1.40.0', os_name='linux', arch='amd64')
        self.assertIn('x86_64', url)

    def test_uses_x86_64_for_arm64_on_macos(self) -> None:
        """Should map arm64 to aarch64 on macOS."""
        url = deno._get_deno_url('1.40.0', os_name='darwin', arch='arm64')
        self.assertIn('aarch64', url)

    def test_unsupported_platform_raises_error(self) -> None:
        """Should raise ValueError for unsupported platforms."""
        with self.assertRaises(ValueError) as ctx:
            deno._get_deno_url('1.40.0', os_name='freebsd', arch='x86_64')
        self.assertIn('Unsupported platform', str(ctx.exception))

    def test_default_version_resolves_to_latest(self) -> None:
        """Should resolve DEFAULT to 'latest' in URL using GitHub redirect."""
        url = deno._get_deno_url(C.DEFAULT, os_name='linux', arch='x86_64')
        self.assertIn('releases/latest/download', url)

    def test_latest_version_uses_redirect(self) -> None:
        """Should use /releases/latest/download for 'latest' version."""
        url = deno._get_deno_url('latest', os_name='linux', arch='x86_64')
        self.assertIn('releases/latest/download', url)

    def test_specific_version_uses_tag(self) -> None:
        """Should use /releases/download/vX.X.X for specific version."""
        url = deno._get_deno_url('1.40.0', os_name='linux', arch='x86_64')
        self.assertIn('releases/download/v1.40.0', url)


if __name__ == '__main__':
    unittest.main()
