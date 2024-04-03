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
    """A file system entry, representing a file or directory in a partition."""

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
        line: str,
        partition: Partition,
        parent: FsEntry | None = None,
        case_insensitive: bool | None = None,
    ) -> Self:
        """Creates a `FsEntry` instance from a line of the output of `fls`."""
        if (m := cls._RE_ENTRY.match(line)) is None:
            raise ValueError(f"Invalid fs entry string: {line}")
        LOGGER.debug(f"Creating FsEntry from string: {line}")
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
        """The numeric inode of the entry."""
        return self.meta_address.inode

    @cached_property
    def is_directory(self) -> bool:
        """Whether the entry is a directory."""
        return self.type_filename.is_directory or self.type_metadata.is_directory

    @cached_property
    def name_path(self) -> PurePath:
        """The entry name with the correct underlying PurePath implementation (Windows/Posix)."""
        return (PureWindowsPath if self.case_insensitive else PurePosixPath)(self.name)

    @cached_property
    def path(self) -> PurePath:
        """The full path of the entry, including the parent path if available."""
        return self.parent.path / self.name_path if self.parent else self.name_path

    @cache
    def name_eq(self, name: str) -> bool:
        """Checks if the entry name is equal to the given name, optionally case-insensitive."""
        if self.case_insensitive:
            return self.name.lower() == name.lower()
        return self.name == name

    @cache
    def name_matches(self, pattern: str) -> bool:
        """Checks if the entry name matches the given glob pattern."""
        return self.name_path.match(pattern)

    @cache
    def children(self) -> FsEntryList:
        """Returns the children of the entry, if it is a directory. Raises ValueError otherwise."""
        if not self.is_directory:
            raise ValueError(f"'{self.path}' is not a directory")
        return FsEntryList.from_partition(self.partition, self, self.case_insensitive)

    @cache
    def child(self, name: str) -> FsEntry:
        """Returns the child entry with the given name. Raises IndexError if not found."""
        children = self.children()
        return children.find_entry(name)

    @cache
    def children_find(self, name: str) -> FsEntryList:
        """Returns the children entries with the given name (supports glob patterns)."""
        children = self.children()
        return children.find_entries(name)

    @cache
    def children_path(self, path: str | PurePath) -> FsEntryList:
        """Returns the children entries with the given path (supports glob patterns)."""
        children = self.children()
        return children.find_path(path)

    def dump_file(self) -> bytes:
        """Dumps the contents of the file to a bytes object using `icat`.
        Raises ValueError if the entry is a directory."""
        if self.is_directory:
            raise ValueError(f"'{self.path}' is a directory")
        LOGGER.info(f"Extracting file '{self.path}'")
        return icat(self.partition, self.meta_address)

    def save_dir(
        self, base_path: str | Path | None = None, parents: bool = False
    ) -> tuple[Path, int, int]:
        """Recursively saves the contents of the directory to the given base path.
        If `parents` is True, the parent path is included in the base path.
        Returns the base path, the number of files saved, and the number of directories saved."""
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
    ) -> tuple[Path | None, int]:
        """Saves the contents of the file entry to the given file path,
        relative to the base path if provided.
        If `file` is None, the file name is inferred from the entry name.
        If `parents` is True, the parent path is included in the base path.
        Returns the file path and the number of bytes written."""

    @overload
    def save_file(self, file: BinaryIO) -> tuple[Path | None, int]:
        """Saves the contents of the file entry to the given file-like object.
        Returns the file path and the number of bytes written."""

    def save_file(
        self,
        file: str | Path | BinaryIO | None = None,
        base_path: str | Path | None = None,
        parents: bool = False,
    ) -> tuple[Path | None, int]:
        """Saves the contents of the file entry to the given file path or file-like object,
        relative to the base path if provided.
        If `file` is None, the file name is inferred from the entry name.
        If `parents` is True, the parent path is included in the base path.
        Returns the file path and the number of bytes written."""
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
        """The attributes of the entry as a string (`deleted`, `reallocated`)."""
        attribs: list[str] = []
        if self.is_deleted:
            attribs.append("deleted")
        if self.is_reallocated:
            attribs.append("reallocated")
        return f" ({', '.join(attribs)})" if attribs else ""

    def short_desc(self) -> str:
        """A short description of the entry: `type_filename/type_metadata: path (attributes?)`."""
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
    """A list of file system entries, representing files or directories in a partition.
    Provides methods to search and save entries, and acts as a container of `FsEntry` instances."""

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
        """Finds the entry with the given name. Raises IndexError if not found."""
        if (entry := next((f for f in self.entries if f.name_eq(name)), None)) is None:
            raise IndexError(f"No entry found with name '{name}'")
        LOGGER.debug(f"Found entry: '{entry}'")
        return entry

    @cache
    def find_entries(self, name: str) -> FsEntryList:
        """Finds all entries with the given name (supports glob patterns)."""
        if entries := [ent for ent in self.entries if ent.name_matches(name)]:
            LOGGER.debug(f"Found entries: {', '.join(str(entry.path) for entry in entries)}")
        else:
            LOGGER.debug(f"No entries found with name matching '{name}'")
        return FsEntryList(entries)

    @cache
    def find_path(self, path: str | PurePath) -> FsEntryList:
        """Finds all entries with the given path (supports glob patterns)."""
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
        """Recursively saves all entries to the given base path."""
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
        """Creates an empty `FsEntryList` instance."""
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
