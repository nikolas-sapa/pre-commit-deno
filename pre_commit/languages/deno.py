from __future__ import annotations

import contextlib
import functools
import os
import platform
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Generator
from collections.abc import Sequence

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.envcontext import PatchesT
from pre_commit.envcontext import Var
from pre_commit.prefix import Prefix
from pre_commit.util import make_executable


ENVIRONMENT_DIR = 'deno_env'
health_check = lang_base.basic_health_check
run_hook = lang_base.basic_run_hook


@functools.lru_cache(maxsize=1)
def get_default_version() -> str:
    # If deno is already installed, we can save setup time by using it
    if lang_base.exe_exists('deno'):
        return 'system'
    else:
        return C.DEFAULT


def get_env_patch(venv: str) -> PatchesT:
    """Get environment patches for the Deno environment."""
    bin_path = os.path.join(venv, 'bin')
    return (
        ('PATH', (bin_path, os.pathsep, Var('PATH'))),
    )


@contextlib.contextmanager
def in_env(prefix: Prefix, version: str) -> Generator[None]:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    with envcontext(get_env_patch(envdir)):
        yield


def _resolve_deno_version(version: str) -> str:
    """Resolve the version string for URL construction.

    Returns 'latest' for DEFAULT version, which uses GitHub's
    /releases/latest redirect to get the most recent release.
    Otherwise returns the version string as-is.
    """
    if version == C.DEFAULT:
        return 'latest'
    return version


def _get_deno_url(
        version: str,
        os_name: str | None = None,
        arch: str | None = None,
) -> str:
    """Get the download URL for a specific Deno version and platform.

    Args:
        version: The Deno version (or 'latest' for default).
                 When 'latest', the URL uses a special redirect that
                 resolves to the most recent release.
        os_name: Override OS name (for testing). Defaults to current platform.
        arch: Override architecture (for testing). Defaults to current machine.
    """
    version = _resolve_deno_version(version)
    os_name = os_name or platform.system().lower()
    arch = arch or platform.machine().lower()

    # Map platform.machine() values to Deno's naming
    arch_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64',
        'aarch64': 'aarch64',
        'arm64': 'aarch64',
    }
    arch = arch_map.get(arch, arch)

    # Deno uses .zip format for all platforms (as of 2024)
    # For 'latest', GitHub redirects to the actual latest release
    if version == 'latest':
        url_prefix = f'https://github.com/denoland/deno/releases/latest/download/deno-{arch}'
    else:
        url_prefix = f'https://github.com/denoland/deno/releases/download/v{version}/deno-{arch}'

    if os_name == 'windows':
        return f'{url_prefix}-pc-windows-msvc.zip'
    elif os_name == 'darwin':
        return f'{url_prefix}-apple-darwin.zip'
    elif os_name == 'linux':
        return f'{url_prefix}-unknown-linux-gnu.zip'
    else:
        raise ValueError(f'Unsupported platform: {os_name}')


def _install_deno_binary(version: str, dest: str) -> None:
    """Download and install Deno binary to the destination directory."""
    url = _get_deno_url(version)

    # Deno releases are all .zip format as of 2024
    archive_ext = '.zip'
    # Windows uses deno.exe, other platforms use 'deno'
    exe_name = 'deno.exe' if sys.platform == 'win32' else 'deno'

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, f'deno{archive_ext}')
        try:
            with urllib.request.urlopen(url) as resp:
                with open(archive_path, 'wb') as f:
                    shutil.copyfileobj(resp, f)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(
                    f'Could not find Deno version {version} for your '
                    f'platform. Visit '
                    f'https://github.com/denoland/deno/releases for '
                    f'available versions.',
                )
            raise

        # Extract zip archive
        with zipfile.ZipFile(archive_path, 'r') as archive:
            archive.extractall(tmpdir)

        # Find the deno binary using os.walk
        found = False
        for root, dirs, files in os.walk(tmpdir):
            if exe_name in files:
                src = os.path.join(root, exe_name)
                os.makedirs(dest, exist_ok=True)
                dst = os.path.join(dest, exe_name)
                shutil.move(src, dst)
                if sys.platform != 'win32':
                    make_executable(dst)
                found = True
                break

        if not found:
            # Binary not found - try without .exe extension
            for root, dirs, files in os.walk(tmpdir):
                if 'deno' in files:
                    src = os.path.join(root, 'deno')
                    os.makedirs(dest, exist_ok=True)
                    dst = os.path.join(dest, exe_name)
                    shutil.move(src, dst)
                    if sys.platform != 'win32':
                        make_executable(dst)
                    found = True
                    break

        if not found:
            raise RuntimeError(
                f'Could not find deno binary in downloaded archive '
                f'for version {version} from {url}'
            )


def install_environment(
        prefix: Prefix,
        version: str,
        additional_dependencies: Sequence[str],
) -> None:
    """Install Deno environment.

    Deno is a single-binary runtime with no package manager.
    For 'system' version, it just verifies the system has deno.
    For specific versions, it downloads and installs the deno binary.
    """
    lang_base.assert_no_additional_deps('deno', additional_dependencies)

    env_dir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    bin_dir = os.path.join(env_dir, 'bin')

    if version == 'system':
        # Verify system deno is available (it's already in PATH)
        health_check(prefix, version)
        # Still create the bin dir for consistency
        os.makedirs(bin_dir, exist_ok=True)
        return

    # Download and install deno for specific version
    _install_deno_binary(version, bin_dir)

    # Verify installation
    health_check(prefix, version)
