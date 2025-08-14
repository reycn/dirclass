from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence
import fnmatch
import logging


logger = logging.getLogger("dirclass")
if not logger.handlers:
    # Configure a default handler if the host app hasn't
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _ensure_patterns(patterns: str | Sequence[str] | None) -> List[str]:
    if patterns is None:
        return ["*"]
    if isinstance(patterns, str):
        return [patterns]
    return list(patterns) if patterns else ["*"]


def _iter_files(root: Path, recursive: bool) -> Iterator[Path]:
    if recursive:
        yield from (p for p in root.rglob("*") if p.is_file())
    else:
        yield from (p for p in root.iterdir() if p.is_file())


def _filter_files(files: Iterable[Path], patterns: Sequence[str]) -> List[Path]:
    if not patterns or patterns == ["*"]:
        return list(files)
    matched: List[Path] = []
    for f in files:
        name = f.name
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                matched.append(f)
                break
    return matched


@dataclass
class DirClass:
    """Dataclass-like wrapper around a directory.

    Provides helpers to list and read files with optional pattern filtering.
    """

    root: Path
    recursive: bool = True
    default_file_types: List[str] | None = None
    _subdir_name_to_path: Dict[str, Path] = field(default_factory=dict, init=False, repr=False)

    def all(self, file_types: str | Sequence[str] | None = None) -> List[str]:
        """Return a flattened list of file paths as strings.

        Args:
            file_types: Glob pattern(s) like "*.py" or ["*.py", "*.md"].
                If omitted, falls back to what was provided at construction,
                otherwise matches all ("*").
        """
        patterns = _ensure_patterns(file_types or self.default_file_types)
        files = _iter_files(self.root, self.recursive)
        filtered = _filter_files(files, patterns)
        return [str(p) for p in filtered]

    def read_all(self, file_types: str | Sequence[str] | None = None) -> List[str]:
        """Return a flattened list of file contents as strings.

        On any read error, log and continue.
        """
        patterns = _ensure_patterns(file_types or self.default_file_types)
        files = _filter_files(_iter_files(self.root, self.recursive), patterns)
        contents: List[str] = []
        for path in files:
            try:
                contents.append(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - we log and continue by design
                logger.warning("Failed to read %s: %s", path, exc)
                continue
        return contents

    # ----- Dynamic subfolder attributes -----
    def __post_init__(self) -> None:
        """Index immediate subfolders and expose them as dynamic attributes.

        Attribute access like `instance.src` returns a list[str] of files
        under `<root>/src`, filtered by the instance's default file types and
        recursion setting. Names are sanitized to valid Python identifiers. In
        case of conflicts with existing attributes or duplicate names after
        sanitization, the entry is skipped and a message is logged.
        """
        try:
            for child in self.root.iterdir():
                if not child.is_dir():
                    continue
                # Generate attribute candidates: full name, last segment after '.',
                # and case-insensitive variants for both.
                name_full = _sanitize_attribute_name(child.name)
                name_tail = _sanitize_attribute_name(child.name.split('.')[-1]) if '.' in child.name else None
                candidates: List[str] = []
                for nm in [name_full, name_tail]:
                    if not nm:
                        continue
                    if nm not in candidates:
                        candidates.append(nm)
                    lower_nm = nm.lower()
                    if lower_nm and lower_nm not in candidates:
                        candidates.append(lower_nm)

                for cand in candidates:
                    if hasattr(self, cand):
                        # conflicts with real attribute/method
                        logger.info("Skipping subdirectory attribute due to conflict: %s -> %s", child.name, cand)
                        continue
                    existing = self._subdir_name_to_path.get(cand)
                    if existing is not None and existing != child:
                        # Different folders mapping to same attribute candidate; skip
                        logger.info("Skipping subdirectory attribute due to duplicate candidate %s from %s (already %s)", cand, child.name, existing.name)
                        continue
                    self._subdir_name_to_path[cand] = child
        except Exception as exc:  # defensive: listing may fail due to permissions, etc.
            logger.warning("Failed to index subdirectories for %s: %s", self.root, exc)

    def __getattr__(self, name: str):
        # Called only if normal attribute access fails
        subdir = self._subdir_name_to_path.get(name)
        if subdir is None:
            # Try sanitized and case-insensitive lookups for convenience
            sanitized = _sanitize_attribute_name(name)
            subdir = (
                self._subdir_name_to_path.get(sanitized)
                or self._subdir_name_to_path.get(name.lower())
                or self._subdir_name_to_path.get(sanitized.lower())
            )
        if subdir is not None:
            patterns = _ensure_patterns(self.default_file_types)
            files = _filter_files(_iter_files(subdir, self.recursive), patterns)
            return [str(p) for p in files]
        raise AttributeError(f"{type(self).__name__!s} object has no attribute {name!r}")

    def __dir__(self) -> List[str]:
        # Improve autocompletion by including dynamic attributes
        base = set(super().__dir__())
        return sorted(base | set(self._subdir_name_to_path.keys()))


def dirclass(father_folder_path: str | Path,
             recursive: bool = True,
             file_types: str | Sequence[str] | None = "*") -> DirClass:
    """Factory function that returns a `DirClass` instance.

    Args:
        father_folder_path: Directory to scan.
        recursive: Whether to recurse into subfolders.
        file_types: Default glob pattern(s) for filtering.
    """
    root = Path(father_folder_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")
    default_patterns = _ensure_patterns(file_types)
    return DirClass(root=root, recursive=recursive, default_file_types=default_patterns)


def _sanitize_attribute_name(name: str) -> str:
    """Convert arbitrary folder names to safe attribute identifiers.

    Non-alphanumeric characters are converted to underscores. If the name starts
    with a digit, an underscore is prefixed. Empty results are returned as an
    empty string so callers can decide to skip.
    """
    if not name:
        return ""
    cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    # Collapse multiple underscores for cleanliness
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


