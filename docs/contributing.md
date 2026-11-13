# Contributing

The public API is organized by H3 category: Indexing, Inspection, Traversal,
Hierarchy, Regions, Directed edges, Vertexes, Geometry, and Miscellaneous.
Each category lives in its matching `src/h3v_*.py` module. The placeholder
categories have an empty `__all__` until their functions are implemented.

Dedicated helpers stay with their category. `src/_h3v_core.py` contains shared
validation, radial packing/decoding, exact-ratio helpers, and model constants;
it imports no category modules. `src/h3v.py` re-exports the public API in
category order, so callers can continue to use `import h3v`.

Public API descriptions come from the implementation function docstrings. Write user documentation using the
[documentation guidelines](documentation_guidelines.md).

## Set up a development environment

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
```

The documentation tools are optional. Install with `-e .` instead if you only
need to work on the library. Python 3.10 or later runs the library; use
Python 3.12 or later for the documentation build shown here.

## Run the library tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover index encoding, signed altitude intervals, hierarchy, conversions,
boundaries, volume, and straight-line geometry. NumPy-specific cases run when
NumPy is installed; it is not a runtime dependency of H3V.

## Build and check the documentation

```powershell
.\.venv\Scripts\python.exe -m sphinx -b html -n -W --keep-going docs docs/_build/html
.\.venv\Scripts\python.exe -m sphinx -b doctest -n -W --keep-going docs docs/_build/doctest
```

The HTML command treats warnings and unresolved references as errors. The
doctest command runs examples in the documentation and public docstrings.
The quick reference and detailed entries use Sphinx autosummary and autodoc,
so edit the Python docstrings when changing a function description.

Generated files under `docs/_build/` are ignored by Git. Do not edit them.

## Preview locally

Open `docs/_build/html/index.html`, or start a local server:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory docs/_build/html
```

Keep that command running and open <http://127.0.0.1:8000/>. The server is
accessible only on your computer. Stop it with `Ctrl+C`. Rebuild the HTML and
refresh the browser after editing documentation.

## Continuous integration and publishing

The GitHub workflow runs library tests on Linux and Windows with Python 3.10,
3.12, and 3.14. A separate job builds the documentation and checks its examples.
It does not deploy the HTML to GitHub Pages.

Commit documentation sources with related API changes. Pushing a commit uploads
those sources; it does not publish the generated website. Software release tags
must match the version in `pyproject.toml`. The encoded index format has its own
version, described in the [format specification](format.md).

## Verify a preview wheel in a clean environment

Version 0.1.0 is an experimental preview under Apache License 2.0. It uses
H3 4.5.0. Public API and serialized-index compatibility are not yet guaranteed.

From the repository root in PowerShell, using a new environment directory:

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir build/release
.\.venv\Scripts\python.exe -m venv build/release-check
.\build\release-check\Scripts\python.exe -m pip install build/release/h3v-0.1.0-py3-none-any.whl
.\build\release-check\Scripts\python.exe -m pip check
.\build\release-check\Scripts\python.exe -I -c "import h3v; print(h3v.__file__)"
.\build\release-check\Scripts\python.exe -I -m unittest discover -s tests -v
```

The printed import path must be inside `build/release-check/Lib/site-packages`,
not this repository's `src` directory. NumPy-specific tests are optional and
are skipped unless NumPy is installed in that environment. CI also builds
and installs the wheel before running the test matrix.

## Prepare a public snapshot without development history

Keep the development checkout as a private working copy. To generate a separate
source snapshot and ZIP, without altering this checkout:

```powershell
.\.venv\Scripts\python.exe tools/export_preview.py
```

The output is `build/public-preview/` and `build/public-preview.zip`. Only
allowlisted project sources, documentation, tests, tools, and license files
are exported. Git metadata, environments, generated documentation, test reports,
and local editor settings are omitted. Ordinary Python comments are removed
after verifying that the Python syntax tree is unchanged; API docstrings and
license notices are retained. They are public documentation and attribution,
not private developer comments. The original checkout is not modified.

Review the exported files and replace repository links if publishing under a
different GitHub name. Create a new, empty GitHub repository rather than a fork.
Then, from the exported directory:

```powershell
Set-Location build/public-preview
git init -b main
git add .
git diff --cached --stat
git commit -m "H3V 0.1.0 experimental preview"
git remote add origin https://github.com/piglabsai/h3v.git
git push -u origin main
```

After the new repository's CI checks pass, create a tag on that tested commit:

```powershell
git tag -a v0.1.0 -m "H3V 0.1.0 experimental preview"
git push origin v0.1.0
```

On GitHub, create a release from that tag, use the matching changelog entry,
mark it as a pre-release, and attach the verified wheel. This publishes only
the new repository's history. It does not erase the original repository's
history, GitHub comments, existing forks, downloaded copies, or caches.
Do not delete the development repository or rewrite its history as part of
this workflow. Existing public forks remain outside this export's control.
