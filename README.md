# Deno Language Support for pre-commit

Implementation of [Deno](https://deno.com) as a first-class language for the
[pre-commit](https://pre-commit.com) framework, addressing
[pre-commit/pre-commit#3410](https://github.com/pre-commit/pre-commit/issues/3410).

## Files

```
pre-commit-deno/
├── pre_commit/
│   ├── all_languages.py          # Registry including 'deno'
│   └── languages/
│       └── deno.py               # Core implementation
└── tests/
    └── languages/
        └── deno_test.py          # Unit tests
```

## Usage

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: deno-lint
        name: Deno Lint
        entry: deno lint
        language: deno
        files: \.ts$

  - repo: https://github.com/example/deno-hooks
    rev: v1.0.0
    hooks:
      - id: format
        language: deno
        language_version: 2.1.4    # or 'system' / default
        entry: deno fmt
        files: \.ts$
```

## Behavior

- `language_version: system` — uses a Deno already on `PATH`.
- default — uses system Deno when present, otherwise downloads the latest
  release via GitHub's `/releases/latest/download/` redirect.
- specific version — downloads that release from GitHub releases (zip format
  on all platforms: `deno-{arch}-pc-windows-msvc.zip`,
  `deno-{arch}-apple-darwin.zip`, `deno-{arch}-unknown-linux-gnu.zip`).
- `x86_64`/`amd64` and `aarch64`/`arm64` machines are supported.

## Design notes

Deno is a single-binary runtime (like Go), so no package-manager /
virtualenv machinery is needed: the module downloads the release archive,
extracts the binary into `{env}/bin`, and adds that directory to `PATH` via
the standard `envcontext`/`in_env` mechanism. `additional_dependencies` is
rejected the same way other self-contained languages do.

## Testing

```bash
python -m py_compile pre_commit/languages/deno.py tests/languages/deno_test.py
# inside a pre-commit checkout with dev deps:
pytest tests/languages/deno_test.py -v
```
