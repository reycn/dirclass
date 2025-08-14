"""A tiny library to treat a directory like a dataclass.

Usage example:

    from dirclass import dirclass

    d = dirclass("/some/path", recursive=True, file_types=["*.py", "*.md"])
    file_paths = d.all()                  # list[str]
    file_contents = d.read_all()          # list[str]

"""

from .core import DirClass, dirclass

__all__ = ["dirclass", "DirClass"]


