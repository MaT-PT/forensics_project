from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from functools import cache, cached_property
from typing import Iterator, Literal, NewType, TypeAlias, overload

from utils import pretty_size

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


@dataclass(frozen=True)
class Partition:
    id: int
    slot: str
    start: Sectors
    end: Sectors
    length: Sectors
    description: str
    partition_table: PartitionTable

    RE_PARTITION = re.compile(r"^\s*(\d+):\s*(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+)$")

    @classmethod
    def from_str(cls, s: str, partition_table: PartitionTable) -> Partition:
        m = Partition.RE_PARTITION.match(s)
        if m is None:
            raise ValueError(f"Invalid partition string: {s}")
        id = int(m.group(1))
        slot = m.group(2)
        start = Sectors(int(m.group(3)))
        end = Sectors(int(m.group(4)))
        length = Sectors(int(m.group(5)))
        description = m.group(6)
        return cls(id, slot, start, end, length, description, partition_table)

    @cached_property
    def start_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.start)

    @cached_property
    def end_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.end)

    @cached_property
    def length_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.length)

    def __str__(self) -> str:
        return (
            f"{self.id:03}: {self.slot:7}  {self.start:>11} ({pretty_size(self.start_bytes):>5})  "
            f"{self.end:>11} ({pretty_size(self.end_bytes):>5})  {self.length:>11} "
            f"({pretty_size(self.length_bytes):>5})  {self.description}"
        )


@dataclass(frozen=True)
class PartitionTable:
    image_file: str
    part_table_type: PartTableType
    partitions: list[Partition]
    offset: Sectors = Sectors(0)
    sector_size: int = 512

    RE_OFFSET = re.compile(r"^\s*Offset Sector: (\d+)\s*$")
    RE_SECTOR_SIZE = re.compile(r"^\s*Units are in (\d+)-byte sectors\s*$")

    @classmethod
    def from_str(cls, s: str, image_file: str) -> PartitionTable:
        lines = s.splitlines()
        part_table_type = PartTableType.from_str(lines.pop(0))
        m = PartitionTable.RE_OFFSET.match(lines.pop(0))
        if m is None:
            raise ValueError("Could not find partition table offset")
        offset = Sectors(int(m.group(1)))
        m = PartitionTable.RE_SECTOR_SIZE.match(lines.pop(0))
        if m is None:
            raise ValueError("Could not find sector size")
        sector_size = int(m.group(1))
        part_table = cls(image_file, part_table_type, [], offset, sector_size)
        for line in lines:
            try:
                part = Partition.from_str(line, part_table)
                part_table.partitions.append(part)
            except ValueError as e:
                print(f"(skipped line: {e})")
        return part_table

    def sectors_to_bytes(self, sectors: Sectors) -> int:
        return sectors * self.sector_size

    @cached_property
    def offset_bytes(self) -> int:
        return self.sectors_to_bytes(self.offset)

    def __str__(self) -> str:
        return (
            f"* Type: {self.part_table_type} [{self.part_table_type.value}]\n"
            f"* Offset: {self.offset} ({self.offset_bytes} B)\n"
            f"* Sector size: {self.sector_size} B\n"
            "* Partitions:\n"
            "    ID : Slot     Start       (bytes)  End         (bytes)  "
            "Length      (bytes)  Description\n"
        ) + "\n".join(f"  * {str(p)}" for p in self.partitions)


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


@dataclass(frozen=True)
class FsEntry:
    name: str
    meta_address: MetaAddress
    type_filename: FsEntryType
    type_metadata: FsEntryType
    partition: Partition
    is_deleted: bool = False
    is_reallocated: bool = False
    parent: FsEntry | None = None
    case_insensitive: bool = False

    RE_ENTRY = re.compile(r"^(.)/(.) (?:(\*) )?([^*]+?)(\(realloc\))?:\t(.+)$")

    @classmethod
    def from_str(
        cls,
        s: str,
        partition: Partition,
        parent: FsEntry | None = None,
        case_insensitive: bool | None = None,
    ) -> FsEntry:
        m = FsEntry.RE_ENTRY.match(s)
        if m is None:
            raise ValueError(f"Invalid fs entry string: {s}")
        type_filename = FsEntryType(m.group(1))
        type_metadata = FsEntryType(m.group(2))
        is_deleted = m.group(3) is not None
        meta_address = MetaAddress(m.group(4))
        is_reallocated = m.group(5) is not None
        name = m.group(6)
        return cls(
            name,
            meta_address,
            type_filename,
            type_metadata,
            partition,
            is_deleted,
            is_reallocated,
            parent,
            (
                case_insensitive
                if case_insensitive is not None
                else (parent.case_insensitive if parent is not None else False)
            ),
        )

    @cached_property
    def inode(self) -> int:
        return self.meta_address.inode

    @cached_property
    def is_directory(self) -> bool:
        return self.type_filename in (
            FsEntryType.DIRECTORY,
            FsEntryType.VIRTUAL_DIRECTORY,
        ) or self.type_metadata in (FsEntryType.DIRECTORY, FsEntryType.VIRTUAL_DIRECTORY)

    @cached_property
    def path(self) -> str:
        return f"{self.parent.path}/{self.name}" if self.parent else self.name

    def name_eq(self, name: str) -> bool:
        if self.case_insensitive:
            return self.name.lower() == name.lower()
        return self.name == name

    def children(self, recursive: bool = False) -> FsEntryList:
        if not self.is_directory:
            raise ValueError(f"{self.path} is not a directory")
        return fls(self.partition, self, recursive, self.case_insensitive)

    def child(self, name: str) -> FsEntry:
        children = self.children()
        return children.find_entry(name)

    def __str__(self) -> str:
        attribs: list[str] = []
        if self.is_deleted:
            attribs.append("deleted")
        if self.is_reallocated:
            attribs.append("reallocated")
        attribs_str = f" ({', '.join(attribs)})" if attribs else ""
        return (
            f"{self.type_filename.value}/{self.type_metadata.value} "
            f"{self.meta_address.address}: {self.name}{attribs_str} ({self.path})"
        )


@dataclass(frozen=True)
class FsEntryList:
    entries: list[FsEntry]

    def find_entry(self, name: str) -> FsEntry:
        res = next((f for f in self.entries if f.name_eq(name)), None)
        if res is None:
            raise IndexError(f"No entry found with name {name}")
        return res

    def __iter__(self) -> Iterator[FsEntry]:
        return iter(self.entries)

    def __contains__(self, item: str) -> bool:
        return any(f.name == item for f in self.entries)

    @overload
    def __getitem__(self, item: int | str) -> FsEntry: ...
    @overload
    def __getitem__(self, item: slice) -> FsEntryList: ...

    def __getitem__(self, item: int | slice | str) -> FsEntry | FsEntryList:
        if isinstance(item, str):
            return self.find_entry(item)
        res = self.entries[item]
        if isinstance(res, list):
            return FsEntryList(res)
        return res

    def __len__(self) -> int:
        return len(self.entries)

    def __str__(self) -> str:
        return "\n".join(str(e) for e in self.entries)


def mmls(
    image_file: str,
    vstype: VsType | None = None,
    imgtype: ImgType | None = None,
    sector_size: int | None = None,
    offset: int | None = None,
) -> PartitionTable:
    args: list[str] = []
    if vstype is not None:
        args += ["-t", vstype]
    if imgtype is not None:
        args += ["-i", imgtype]
    if sector_size is not None:
        args += ["-b", str(sector_size)]
    if offset is not None:
        args += ["-o", str(offset)]
    args.append(image_file)

    try:
        res = subprocess.check_output(["mmls"] + args, encoding="utf-8")
        # print(res)
        return PartitionTable.from_str(res, image_file)
    except subprocess.CalledProcessError as e:
        print(f"Error running mmls: {e}")
        exit(e.returncode)


def fls(
    partition: Partition,
    root: FsEntry | None = None,
    recursive: bool = False,
    case_insensitive: bool = False,
) -> FsEntryList:
    args = ["-p"]  # Show full path
    args += ["-o", str(partition.start)]  # Image offset
    if recursive:
        args.append("-r")
    args.append(partition.partition_table.image_file)
    if root is not None:
        args.append(str(root.inode))

    try:
        res = subprocess.check_output(["fls"] + args, encoding="utf-8")
        # print(res)
        return FsEntryList(
            [FsEntry.from_str(line, partition, root, case_insensitive) for line in res.splitlines()]
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running fls: {e}")
        exit(e.returncode)
