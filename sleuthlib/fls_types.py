from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path, PurePath
from typing import BinaryIO, Iterator, overload

from . import fls_wrapper, icat_wrapper
from .mmls_types import Partition
from .types import FsEntryType, MetaAddress

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
    def path(self) -> str:
        return f"{self.parent.path}/{self.name}" if self.parent else self.name

    @cache
    def name_eq(self, name: str) -> bool:
        if self.case_insensitive:
            return self.name.lower() == name.lower()
        return self.name == name

    @cache
    def children(self) -> FsEntryList:
        if not self.is_directory:
            raise ValueError(f"'{self.path}' is not a directory")
        return fls_wrapper.fls(self.partition, self, self.case_insensitive)

    @cache
    def child(self, name: str) -> FsEntry:
        children = self.children()
        return children.find_entry(name)

    @cache
    def child_path(self, path: str | PurePath) -> FsEntry:
        children = self.children()
        return children.find_path(path)

    def extract_file(self) -> bytes:
        if self.is_directory:
            raise ValueError(f"'{self.path}' is a directory")
        LOGGER.info(f"Extracting file '{self.path}'")
        return icat_wrapper.icat(self.partition, self.meta_address)

    @overload
    def save_dir(self, base_path: str | Path, subdir: bool = False) -> tuple[str, int, int]: ...
    @overload
    def save_dir(self) -> tuple[str, int, int]: ...

    def save_dir(
        self, base_path: str | Path | None = None, subdir: bool = False
    ) -> tuple[str, int, int]:
        if not self.is_directory:
            raise ValueError(f"'{self.path}' is not a directory")
        if base_path is not None:
            base_path = Path(base_path)
            if subdir:
                base_path = base_path / self.name
        else:
            base_path = Path(self.name)
        LOGGER.info(f"Saving contents of '{self.path}' to '{base_path}'")
        base_path.mkdir(exist_ok=True, parents=True)
        nb_files = 0
        nb_dirs = 1
        for child in self.children():
            if child.is_directory:
                _, nf, nd = child.save_dir(base_path=base_path / child.name)
                nb_files += nf
                nb_dirs += nd
            else:
                child.save_file(base_path=base_path)
                nb_files += 1
        LOGGER.info(
            f"Saved {nb_files} file{'s' if nb_files > 1 else ''} and {nb_dirs} "
            f"director{'ies' if nb_dirs > 1 else 'y'} to '{str(base_path)}'"
        )
        return str(base_path), nb_files, nb_dirs

    @overload
    def save_file(
        self, file: str | Path | None = None, base_path: str | Path | None = None
    ) -> tuple[str, int]: ...
    @overload
    def save_file(self, file: BinaryIO) -> tuple[str, int]: ...

    def save_file(
        self, file: str | Path | BinaryIO | None = None, base_path: str | Path | None = None
    ) -> tuple[str, int]:
        must_close = False
        if file is None:
            file = Path(self.name)
        elif isinstance(file, str):
            file = Path(file)
        if isinstance(file, Path):
            if base_path is not None:
                base_path = Path(base_path)
                base_path.mkdir(exist_ok=True, parents=True)
                file = base_path / file
            filepath = str(file)
            file = open(file, "wb")
            must_close = True
        elif base_path is not None:
            raise ValueError("Cannot specify base_path with a file-like object")
        else:
            filepath = file.name if isinstance(file.name, str) else "unknown_file"

        LOGGER.info(f"Saving file '{self.path}' to '{filepath}'")
        try:
            data = self.extract_file()
            res = file.write(data)
            LOGGER.info(f"Written {res} bytes to '{filepath}'")
            return filepath, res
        finally:
            if must_close:
                file.close()

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
            raise IndexError(f"No entry found with name '{name}'")
        LOGGER.debug(f"Found entry '{res}'")
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
