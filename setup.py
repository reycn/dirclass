from __future__ import annotations

import pathlib
import sys

from setuptools import find_packages, setup


ROOT = pathlib.Path(__file__).parent
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"

project_kwargs = {}

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]

    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    proj = data.get("project", {})
    project_kwargs.update(
        name=proj.get("name", "dirclass"),
        version=proj.get("version", "0.0.0"),
        description=proj.get("description", ""),
        classifiers=proj.get("classifiers", []),
        python_requires=proj.get("requires-python", ">=3.8"),
        keywords=proj.get("keywords", []),
    )
except Exception:
    # Minimal fallback
    project_kwargs.update(
        name="dirclass",
        version="0.0.0",
        description="Treat a directory like a dataclass",
        python_requires=">=3.8",
    )

long_description = ""
if README.exists():
    long_description = README.read_text(encoding="utf-8")

setup(
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=["dirclass*"]),
    include_package_data=True,
    **project_kwargs,
)

from setuptools import setup


if __name__ == "__main__":
    # Defer all metadata/config to pyproject.toml (PEP 621)
    setup()
