"""Check a wheel and source distribution before uploading either artifact.

Run with the candidate wheel installed, e.g. python -I tools/check_release.py build/release.
"""

import ast
from email.parser import BytesParser
from importlib import metadata
from pathlib import Path
import re
import tarfile
import zipfile


def check_release(directory):
    directory = Path(directory)
    wheels = list(directory.glob("h3v-*.whl"))
    sources = list(directory.glob("h3v-*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Use a fresh directory containing exactly one H3V wheel and sdist")
    with zipfile.ZipFile(wheels[0]) as wheel, tarfile.open(sources[0]) as source:
        metadata_name, = (n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        package = BytesParser().parsebytes(wheel.read(metadata_name))
        version = package["Version"]
        root = f"h3v-{version}"

        def read_source(name):
            return source.extractfile(f"{root}/{name}").read()

        source_metadata = BytesParser().parsebytes(read_source("PKG-INFO"))
        for key in ("Name", "Version", "Requires-Python", "Requires-Dist", "Project-URL",
                    "License-Expression", "License-File", "Description-Content-Type"):
            if package.get_all(key) != source_metadata.get_all(key):
                raise ValueError(f"Wheel and sdist metadata differ: {key}")
        readme = read_source("README.md").decode("utf-8").replace("\r\n", "\n")
        description = package.get_payload().replace("\r\n", "\n")
        if description.strip() != readme.strip():
            raise ValueError("Wheel description differs from the sdist README")
        if "python -m pip install h3v" not in readme:
            raise ValueError("README must explain installation from PyPI")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
        if not links or any(not link.startswith("https://") for link in links):
            raise ValueError("Published README links must be absolute HTTPS URLs")
        modules = {n for n in wheel.namelist() if n.endswith(".py")}
        source_modules = {Path(n).name for n in source.getnames()
                          if n.startswith(f"{root}/src/") and n.endswith(".py")}
        if modules != source_modules:
            raise ValueError("Wheel and sdist contain different Python modules")
        for name in modules:
            if ast.dump(ast.parse(wheel.read(name))) != ast.dump(ast.parse(read_source(f"src/{name}"))):
                raise ValueError(f"Wheel source differs from the sdist: {name}")
        for name in ("LICENSE", "NOTICE"):
            if wheel.read(f"h3v-{version}.dist-info/licenses/{name}") != read_source(name):
                raise ValueError(f"License file differs: {name}")
        for name in ("docs/index.md", "docs/conf.py", "docs/_static/voxel.svg", "tests/test_core.py"):
            read_source(name)
        if metadata.version("h3v") != version:
            raise ValueError("Install the candidate wheel before checking its examples")
        import h3v
        installed = Path(h3v.__file__).resolve()
        expected = Path(metadata.distribution("h3v").locate_file("h3v.py")).resolve()
        if installed != expected:
            raise ValueError("H3V is imported from a checkout instead of the installed wheel")
        for name in modules:
            installed_source = Path(metadata.distribution("h3v").locate_file(name)).read_bytes()
            if ast.dump(ast.parse(installed_source)) != ast.dump(ast.parse(wheel.read(name))):
                raise ValueError(f"Installed module differs from the candidate wheel: {name}")
        examples = re.findall(r"```python\s*\n(.*?)```", readme, re.DOTALL)
        if not examples:
            raise ValueError("README has no Python example")
        for example in examples:
            exec(compile(example, "README.md", "exec"), {})
        print(f"Verified H3V {version}: wheel, sdist, metadata, links, licenses, and README examples")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    check_release(parser.parse_args().directory)
