from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, Iterable, Iterator, overload

from .icat_wrapper import icat
from .mmls_types import Partition
from .types import FsEntryType, MetaAddress
from .utils import run_program

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LOGGER = logging.getLogger(__name__)


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

    _RE_ENTRY = re.compile(r"^(.)/(.) (?:(\*) )?([^*]+?)(\(realloc\))?:\t(.+)$")

    @classmethod
    def from_str(
        cls,
        s: str,
        partition: Partition,
        parent: FsEntry | None = None,
        case_insensitive: bool | None = None,
    ) -> Self:
        if (m := cls._RE_ENTRY.match(s)) is None:
            raise ValueError(f"Invalid fs entry string: {s}")
        LOGGER.debug(f"Creating FsEntry from string: {s}")
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
    def name_path(self) -> PurePath:
        return (PureWindowsPath if self.case_insensitive else PurePosixPath)(self.name)

    @cached_property
    def path(self) -> PurePath:
        return self.parent.path / self.name_path if self.parent else self.name_path

    @cache
    def name_eq(self, name: str) -> bool:
        if self.case_insensitive:
            return self.name.lower() == name.lower()
        return self.name == name

    @cache
    def name_matches(self, pattern: str) -> bool:
        return self.name_path.match(pattern)

    @cache
    def children(self) -> FsEntryList:
        if not self.is_directory:
            raise ValueError(f"'{self.path}' is not a directory")
        return FsEntryList.from_partition(self.partition, self, self.case_insensitive)

    @cache
    def child(self, name: str) -> FsEntry:
        children = self.children()
        return children.find_entry(name)

    @cache
    def children_find(self, name: str) -> FsEntryList:
        children = self.children()
        return children.find_entries(name)

    @cache
    def children_path(self, path: str | PurePath) -> FsEntryList:
        children = self.children()
        return children.find_path(path)

    def dump_file(self) -> bytes:
        if self.is_directory:
            raise ValueError(f"'{self.path}' is a directory")
        LOGGER.info(f"Extracting file '{self.path}'")
        return icat(self.partition, self.meta_address)

    def save_dir(
        self, base_path: str | Path | None = None, parents: bool = False
    ) -> tuple[Path, int, int]:
        if not self.is_directory:
            raise ValueError(f"'{self.path}' is not a directory")
        path = self.path if parents else self.name_path
        if base_path is None:
            base_path = Path(".")
        else:
            base_path = Path(base_path)
        base_path /= path
        LOGGER.info(f"Saving contents of '{self.path}' to '{base_path}'")
        base_path.mkdir(exist_ok=True, parents=True)
        nb_files = 0
        nb_dirs = 1
        for child in self.children():
            if child.is_directory:
                _, nf, nd = child.save_dir(base_path=base_path)
                nb_files += nf
                nb_dirs += nd
            else:
                child.save_file(base_path=base_path)
                nb_files += 1
        LOGGER.info(
            f"Saved {nb_files} file{'s' if nb_files > 1 else ''} and {nb_dirs} "
            f"director{'ies' if nb_dirs > 1 else 'y'} to '{base_path}'"
        )
        return base_path, nb_files, nb_dirs

    @overload
    def save_file(
        self,
        file: str | Path | None = ...,
        base_path: str | Path | None = ...,
        parents: bool = False,
    ) -> tuple[Path | None, int]: ...
    @overload
    def save_file(self, file: BinaryIO) -> tuple[Path | None, int]: ...

    def save_file(
        self,
        file: str | Path | BinaryIO | None = None,
        base_path: str | Path | None = None,
        parents: bool = False,
    ) -> tuple[Path | None, int]:
        must_close = False
        if file is None:
            file = Path(self.name)
        elif isinstance(file, str):
            file = Path(file)
        if isinstance(file, Path):
            if base_path is None:
                base_path = Path(".")
            else:
                base_path = Path(base_path)
            if parents and self.parent:
                base_path /= self.parent.path
            base_path.mkdir(exist_ok=True, parents=True)
            file = base_path / file
            filepath: Path | None = file
            file = open(file, "wb")
            must_close = True
        elif base_path is not None:
            raise ValueError("Cannot specify base_path with a file-like object")
        elif parents:
            raise ValueError("Cannot specify parents with a file-like object")
        else:
            filepath = Path(file.name) if isinstance(file.name, str) else None

        LOGGER.info(f"Saving file '{self.path}' to '{filepath}'")
        try:
            data = self.dump_file()
            count = file.write(data)
            LOGGER.info(f"Written {count} bytes to '{filepath}'")
            return filepath, count
        finally:
            if must_close:
                file.close()

    @cached_property
    def attributes(self) -> str:
        attribs: list[str] = []
        if self.is_deleted:
            attribs.append("deleted")
        if self.is_reallocated:
            attribs.append("reallocated")
        return f" ({', '.join(attribs)})" if attribs else ""

    def short_desc(self) -> str:
        return (
            f"{self.type_filename.value}/{self.type_metadata.value}: {self.path}{self.attributes}"
        )

    def __str__(self) -> str:
        return (
            f"{self.type_filename.value}/{self.type_metadata.value} "
            f"{self.meta_address.address}: {self.name}{self.attributes} ({self.path})"
        )


@dataclass(frozen=True)
class FsEntryList:
    entries: list[FsEntry]

    @classmethod
    def from_partition(
        cls,
        partition: Partition,
        root: FsEntry | None = None,
        case_insensitive: bool = False,
        **kwargs: Any,
    ) -> Self:
        """Runs the `fls` tool to list files in a partition.

        Args:
            partition: The partition to list files from.
            root: The root entry to list files from.
            case_insensitive: Whether to use case-insensitive matching (for FAT/NFTS partitions)
            **kwargs: Additional arguments to pass to `run_program`.
        """
        args: list[str] = []
        # args += ["-p"]  # Show full path
        args += ["-o", str(partition.start)]  # Image offset
        if partition.partition_table.img_type is not None:
            args += ["-i", partition.partition_table.img_type]  # Image type
        args.extend(partition.partition_table.image_files)
        if root is not None:
            args.append(str(root.meta_address.address))

        res = run_program("fls", args, logger=LOGGER, encoding="utf-8", **kwargs)
        return cls(
            [FsEntry.from_str(line, partition, root, case_insensitive) for line in res.splitlines()]
        )

    @cache
    def find_entry(self, name: str) -> FsEntry:
        if (entry := next((f for f in self.entries if f.name_eq(name)), None)) is None:
            raise IndexError(f"No entry found with name '{name}'")
        LOGGER.debug(f"Found entry: '{entry}'")
        return entry

    @cache
    def find_entries(self, name: str) -> FsEntryList:
        if entries := [ent for ent in self.entries if ent.name_matches(name)]:
            LOGGER.debug(f"Found entries: {', '.join(str(entry.path) for entry in entries)}")
        else:
            LOGGER.debug(f"No entries found with name matching '{name}'")
        return FsEntryList(entries)

    @cache
    def find_path(self, path: str | PurePath) -> FsEntryList:
        if isinstance(path, str):
            path = PurePath(path.replace("\\", "/"))
        if path.is_absolute():
            raise ValueError("Path must be relative")
        parts = path.parts
        entries = self.find_entries(parts[0])
        for part in parts[1:]:
            ent_tmp = FsEntryList.empty()
            for entry in entries:
                if entry.is_directory:
                    ent_tmp += entry.children()
            entries = ent_tmp.find_entries(part)
        return entries

    def save_all(self, base_path: str | Path | None = None) -> tuple[Path, int, int]:
        if base_path is None:
            base_path = Path(".")
        else:
            base_path = Path(base_path)
            base_path.mkdir(exist_ok=True, parents=True)
        nb_files = 0
        nb_dirs = 0
        for entry in self:
            if entry.is_directory:
                _, nf, nd = entry.save_dir(base_path=base_path)
                nb_files += nf
                nb_dirs += nd
            else:
                entry.save_file(base_path=base_path)
                nb_files += 1
        LOGGER.info(
            f"Saved {nb_files} file{'s' if nb_files > 1 else ''} and {nb_dirs} "
            f"director{'ies' if nb_dirs > 1 else 'y'} to '{base_path}'"
        )
        return base_path, nb_files, nb_dirs

    @classmethod
    def empty(cls) -> Self:
        return cls([])

    def __iter__(self) -> Iterator[FsEntry]:
        return iter(self.entries)

    def __contains__(self, item: str | FsEntry) -> bool:
        if isinstance(item, str):
            return any(f.name == item for f in self.entries)
        return item in self.entries

    @overload
    def __getitem__(self, item: int) -> FsEntry: ...
    @overload
    def __getitem__(self, item: slice | str) -> FsEntryList: ...

    def __getitem__(self, item: int | slice | str) -> FsEntry | FsEntryList:
        if isinstance(item, str):
            return self.find_entries(item)
        if isinstance(res := self.entries[item], list):
            return FsEntryList(res)
        return res

    def __len__(self) -> int:
        return len(self.entries)

    def __add__(self, other: Iterable[FsEntry]) -> FsEntryList:
        return FsEntryList(self.entries + list(other))

    def __radd__(self, other: Iterable[FsEntry]) -> FsEntryList:
        return FsEntryList(list(other) + self.entries)

    def __str__(self) -> str:
        return "\n".join(str(e) for e in self.entries)

    def __hash__(self) -> int:
        return hash(tuple(self.entries))
