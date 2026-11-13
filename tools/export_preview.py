"""Export a comment-stripped source snapshot without Git metadata or local artifacts."""

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import tokenize


ROOT = Path(__file__).resolve().parents[1]


def strip_comments(source):
    lines = source.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if any(marker in token.string.lower() for marker in ("copyright", "license", "spdx", "#!")):
            continue
        row, start = token.start
        _, end = token.end
        lines[row - 1] = lines[row - 1][:start] + " " * (end - start) + lines[row - 1][end:]
    stripped = "".join(line.rstrip() + "\n" for line in "".join(lines).splitlines())
    if ast.dump(ast.parse(source)) != ast.dump(ast.parse(stripped)):
        raise ValueError("Comment removal changed the Python syntax tree")
    return stripped


def export(destination):
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT / "build"):
        raise ValueError("The export destination must be inside this repository's build directory")
    if destination.exists():
        raise ValueError("Choose a new export directory; existing snapshots are never overwritten")
    top_files = ("README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "pyproject.toml", ".gitignore")
    files = [ROOT / name for name in top_files]
    for directory in ("src", "tests", "docs", ".github", "tools"):
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and not any(part in ("_build", "__pycache__") or part.endswith(".egg-info")
                                                  for part in path.relative_to(ROOT).parts))
    manifest = {}
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Refusing to export a linked or external file: {path}")
        relative = path.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".py":
            target.write_text(strip_comments(path.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            shutil.copyfile(path, target)
        manifest[str(relative)] = hashlib.sha256(target.read_bytes()).hexdigest()
    (destination / "PREVIEW_MANIFEST.json").write_text(json.dumps({
        "version": "0.1.0", "status": "experimental preview",
        "scope": "Allowlisted current source files; no .git history, GitHub discussions, local environments, or reports",
        "comments": "Ordinary Python comments removed; docstrings and license notices retained; Python ASTs verified unchanged",
        "limitations": "This is a source snapshot, not an erasure of existing public forks, clones, caches, or the original repository",
        "files_sha256": manifest,
    }, indent=2), encoding="utf-8")
    archive = shutil.make_archive(str(destination), "zip", root_dir=destination.parent, base_dir=destination.name)
    print(json.dumps({"directory": str(destination), "archive": archive, "files": len(files)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "public-preview")
    export(parser.parse_args().output)
