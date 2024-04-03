from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import cache, cached_property
from typing import Literal, NewType, TypeAlias

PART_TABLE_TYPES = {
    "dos": "DOS Partition Table",
    "mac": "MAC Partition Map",
    "bsd": "BSD Disk Label",
    "sun": "Sun Volume Table of Contents (Solaris)",
    "gpt": "GUID Partition Table (EFI)",
}

IMG_TYPES = {
    "raw": "Single or split raw file (dd)",
    "aff": "Advanced Forensic Format",
    "afd": "AFF Multiple File",
    "afm": "AFF with external metadata",
    "afflib": "All AFFLIB image formats (including beta ones)",
    "ewf": "Expert Witness Format (EnCase)",
    "vmdk": "Virtual Machine Disk (VmWare, Virtual Box)",
    "vhd": "Virtual Hard Drive (Microsoft)",
}

FS_ENTRY_TYPES = {
    "-": "Unknown type",
    "r": "Regular file",
    "d": "Directory",
    "c": "Character device",
    "b": "Block device",
    "l": "Symbolic link",
    "p": "Named FIFO",
    "s": "Shadow",
    "h": "Socket",
    "w": "Whiteout",
    "v": "TSK Virtual file",
    "V": "TSK Virtual directory",
}

Sectors = NewType("Sectors", int)

VsType: TypeAlias = Literal["dos", "mac", "bsd", "sun", "gpt"]
ImgType: TypeAlias = Literal["raw", "aff", "afd", "afm", "afflib", "ewf", "vmdk", "vhd"]


class PartTableType(str, Enum):
    DOS = "dos"
    MAC = "mac"
    BSD = "bsd"
    SUN = "sun"
    GPT = "gpt"
    UNKNOWN = "unknown"

    @staticmethod
    def from_str(s: str) -> PartTableType:
        s = s.strip()
        return next(
            (PartTableType(t) for t, desc in PART_TABLE_TYPES.items() if desc == s),
            PartTableType.UNKNOWN,
        )

    def __str__(self) -> str:
        return PART_TABLE_TYPES.get(self.value, "Unknown")


class FsEntryType(str, Enum):
    UNKNOWN = "-"
    REGULAR = "r"
    DIRECTORY = "d"
    CHARACTER = "c"
    BLOCK = "b"
    SYMLINK = "l"
    FIFO = "p"
    SHADOW = "s"
    SOCKET = "h"
    WHITEOUT = "w"
    VIRTUAL_FILE = "v"
    VIRTUAL_DIRECTORY = "V"

    def __str__(self) -> str:
        return FS_ENTRY_TYPES.get(self.value, "Unknown")


@dataclass(frozen=True)
class MetaAddress:
    """Represents a metadata address in a filesystem.
    In NTFS, this is a string in the form "1304-128-1".
    In other filesystems, this is an integer."""

    address: str

    RE_NTFS_ADDRESS = re.compile(r"^\d+-\d+-\d+$")

    def __post_init__(self) -> None:
        if not (self.address.isdecimal() or MetaAddress.RE_NTFS_ADDRESS.match(self.address)):
            raise ValueError(f"Invalid metadata address: {self.address}")

    @cache
    def is_ntfs(self) -> bool:
        return not self.address.isdecimal()

    @cached_property
    def inode(self) -> int:
        return int(self.address.split("-", 1)[0])
