from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import PurePath
from typing import Iterator, overload

from .mmls import Partition
from .types import FsEntryType


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

    @cache
    def name_eq(self, name: str) -> bool:
        if self.case_insensitive:
            return self.name.lower() == name.lower()
        return self.name == name

    @cache
    def children(self, recursive: bool = False) -> FsEntryList:
        if not self.is_directory:
            raise ValueError(f"{self.path} is not a directory")
        return fls(self.partition, self, recursive, self.case_insensitive)

    @cache
    def child(self, name: str) -> FsEntry:
        children = self.children()
        return children.find_entry(name)

    @cache
    def child_path(self, path: str | PurePath) -> FsEntry:
        children = self.children()
        return children.find_path(path)

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

    @cache
    def find_entry(self, name: str) -> FsEntry:
        res = next((f for f in self.entries if f.name_eq(name)), None)
        if res is None:
            raise IndexError(f"No entry found with name {name}")
        return res

    @cache
    def find_path(self, path: str | PurePath) -> FsEntry:
        if isinstance(path, str):
            path = PurePath(path.replace("\\", "/"))
        if path.is_absolute():
            raise ValueError("Path must be relative")
        parts = path.parts
        current = self.find_entry(parts[0])
        for part in parts[1:]:
            current = current.child(part)
        return current

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

    def __hash__(self) -> int:
        return hash(tuple(self.entries))


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
