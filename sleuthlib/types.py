from __future__ import annotations

from enum import StrEnum
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


class PartTableType(StrEnum):
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


class FsEntryType(StrEnum):
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
