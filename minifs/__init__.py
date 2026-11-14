"""MiniFS: sistema de arquivos simplificado sobre um disco virtual."""

from .errors import *  # noqa: F401,F403
from .fs import DiskUsage, FileInfo, MiniFS  # noqa: F401
from .layout import Layout, compute_layout  # noqa: F401

__version__ = "0.1.0"
