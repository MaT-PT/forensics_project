from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Any, Iterable

from . import fls_types
from .types import ImgType, PartTableType, Sectors, VsType
from .utils import pretty_size, run_program

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Partition:
    """A partition on a disk image, with start and end sectors, length, and description."""

    id: int
    slot: str
    start: Sectors
    end: Sectors
    length: Sectors
    description: str
    partition_table: PartitionTable

    _RE_PARTITION = re.compile(r"^\s*(\d+):\s*(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+)$")

    @classmethod
    def from_str(cls, line: str, partition_table: PartitionTable) -> Self:
        """Creates a `Partition` instance from a line of the output of `mmls`."""
        if (m := cls._RE_PARTITION.match(line)) is None:
            raise ValueError(f"Invalid partition string: {line}")
        LOGGER.debug(f"Creating Partition from string: {line}")
        id = int(m.group(1))
        slot = m.group(2)
        start = Sectors(int(m.group(3)))
        end = Sectors(int(m.group(4)))
        length = Sectors(int(m.group(5)))
        description = m.group(6)
        return cls(id, slot, start, end, length, description, partition_table)

    @cached_property
    def start_bytes(self) -> int:
        """The partition starting offset, in bytes."""
        return self.partition_table.sectors_to_bytes(self.start)

    @cached_property
    def end_bytes(self) -> int:
        """The partition ending offset, in bytes."""
        return self.partition_table.sectors_to_bytes(self.end)

    @cached_property
    def length_bytes(self) -> int:
        """The partition length, in bytes."""
        return self.partition_table.sectors_to_bytes(self.length)

    @cached_property
    def is_filesystem(self) -> bool:
        """Returns whether the partition is a filesystem partition (ie. has a slot number)."""
        return self.slot.replace(":", "").isdecimal()

    @cached_property
    def is_ntfs(self) -> bool:
        """Returns whether the partition is an NTFS partition (ie. has a `$MFT` entry)."""
        try:
            return "$MFT" in self.root_entries(can_fail=True)
        except ChildProcessError:
            return False

    @cache
    def root_entries(
        self, case_insensitive: bool = True, can_fail: bool = False
    ) -> fls_types.FsEntryList:
        """Returns the root entries of the partition, using the `fls` tool.
        Results are cached to avoid unnecessary re-runs of the tool."""
        return fls_types.FsEntryList.from_partition(
            self, case_insensitive=case_insensitive, can_fail=can_fail, silent_stderr=can_fail
        )

    def short_desc(self) -> str:
        """A short description of the partition: `description [ID id, size_bytes]`."""
        return f"{self.description} [ID {self.id}, {pretty_size(self.length_bytes, False)}]"

    def __str__(self) -> str:
        return (
            f"{self.id:03}: {self.slot:7}  {self.start:>11} ({pretty_size(self.start_bytes):>5})  "
            f"{self.end:>11} ({pretty_size(self.end_bytes):>5})  {self.length:>11} "
            f"({pretty_size(self.length_bytes):>5})  {self.description}"
        )

    def __hash__(self) -> int:
        return hash((self.id, self.slot, self.start, self.end, self.length, self.description))


@dataclass(frozen=True)
class PartitionTable:
    """A partition table extracted from a disk image with `mmls`.
    Contains a list of partitions and various metadata."""

    image_files: tuple[str, ...]
    part_table_type: PartTableType
    partitions: list[Partition]
    offset: Sectors = Sectors(0)
    sector_size: int = 512
    img_type: ImgType | None = None

    _RE_OFFSET = re.compile(r"^\s*Offset Sector: (\d+)\s*$")
    _RE_SECTOR_SIZE = re.compile(r"^\s*Units are in (\d+)-byte sectors\s*$")

    @classmethod
    def from_str(cls, s: str, image_files: Iterable[str], imgtype: ImgType | None = None) -> Self:
        """Creates a `PartitionTable` instance from the output of `mmls`."""
        lines = s.splitlines()
        part_table_type = PartTableType.from_str(lines.pop(0))
        if (m := cls._RE_OFFSET.match(lines.pop(0))) is None:
            raise ValueError("Could not find partition table offset")
        offset = Sectors(int(m.group(1)))
        if (m := cls._RE_SECTOR_SIZE.match(lines.pop(0))) is None:
            raise ValueError("Could not find sector size")
        sector_size = int(m.group(1))
        part_table = cls(tuple(image_files), part_table_type, [], offset, sector_size, imgtype)
        for line in lines:
            try:
                part = Partition.from_str(line, part_table)
                part_table.partitions.append(part)
            except ValueError as e:
                LOGGER.debug(f"(Skipped line: {e})")
        return part_table

    @classmethod
    def from_image_files(
        cls,
        image_files: str | Iterable[str],
        vstype: VsType | None = None,
        imgtype: ImgType | None = None,
        sector_size: int | None = None,
        offset: int | None = None,
        **kwargs: Any,
    ) -> Self:
        """Runs the `mmls` tool to extract partition information from an image.

        Args:
            image_files: Path to the image file(s).
            vstype: Volume system type to use (`dos`, `mac`, `bsd`, `sun`, `gpt`).
            imgtype: Image type (`raw`/`aff`/`afd`/`afm`/`afflib`/`ewf`/`vmdk`/`vhd`/`logical`).
            sector_size: Sector size to use.
            offset: Offset to use for the start of the volume.
            **kwargs: Additional arguments to pass to `run_program`.
        """
        args: list[str] = []
        if vstype is not None:
            args += ["-t", vstype]
        if imgtype is not None:
            args += ["-i", imgtype]
        if sector_size is not None:
            args += ["-b", str(sector_size)]
        if offset is not None:
            args += ["-o", str(offset)]
        if isinstance(image_files, str):
            image_files = (image_files,)
        args.extend(image_files)

        res = run_program("mmls", args, logger=LOGGER, encoding="utf-8", **kwargs)
        return cls.from_str(res, image_files, imgtype)

    def sectors_to_bytes(self, sectors: Sectors) -> int:
        """Converts a number of sectors to bytes using the sector size."""
        return sectors * self.sector_size

    @cached_property
    def offset_bytes(self) -> int:
        """The offset of the partition table, in bytes."""
        return self.sectors_to_bytes(self.offset)

    @staticmethod
    def partlist_header() -> str:
        """Returns the column names for the output of `Partition.__str__`."""
        return (
            "ID : Slot           Start (bytes)          End (bytes)  "
            "     Length (bytes)  Description"
        )

    @cache
    def filesystem_partitions(self) -> list[Partition]:
        """Returns the list of filesystem partitions from this partition table."""
        return [p for p in self.partitions if p.is_filesystem]

    def __str__(self) -> str:
        return (
            f"Type: {self.part_table_type} [{self.part_table_type.value}]\n"
            f"Offset: {self.offset} ({self.offset_bytes} B)\n"
            f"Sector size: {self.sector_size} B\n"
            "Partitions:\n"
            f"   {self.partlist_header()}\n"
        ) + "\n".join(f" * {str(p)}" for p in self.partitions)

    def __hash__(self) -> int:
        return hash(
            (
                self.image_files,
                self.part_table_type,
                self.offset,
                self.sector_size,
                tuple(self.partitions),
            )
        )
