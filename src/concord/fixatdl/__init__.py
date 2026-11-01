"""FIXatdl 1.1 reader and writer.

FIXatdl (FIX Algorithmic Trading Definition Language) is the FIX Trading
Community's XML format for describing algo strategies, their parameters, their
on-screen layout and their validation rules.
"""

from concord.fixatdl.read import FixatdlError, ReadResult, read_fixatdl, read_fixatdl_file
from concord.fixatdl.write import write_fixatdl

__all__ = ["FixatdlError", "ReadResult", "read_fixatdl", "read_fixatdl_file", "write_fixatdl"]
