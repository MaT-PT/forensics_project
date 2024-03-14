from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Iterable

from . import fls_types, fls_wrapper
from .types import ImgType, PartTableType, Sectors
from .utils import pretty_size

LOGGER = logging.getLogger(__name__)


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
        LOGGER.debug(f"Creating Partition from string: {s}")
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

    @cached_property
    def is_filesystem(self) -> bool:
        return self.slot.isdecimal()

    @cached_property
    def partition_number(self) -> int | None:
        return int(self.slot) if self.is_filesystem else None

    @cache
    def root_entries(self, case_insensitive: bool = True) -> fls_types.FsEntryList:
        return fls_wrapper.fls(self, case_insensitive=case_insensitive)

    @cache
    def short_desc(self) -> str:
        return f"{self.description} (ID {self.id}, {self.length_bytes} bytes)"

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
    image_files: tuple[str, ...]
    part_table_type: PartTableType
    partitions: list[Partition]
    offset: Sectors = Sectors(0)
    sector_size: int = 512
    img_type: ImgType | None = None

    RE_OFFSET = re.compile(r"^\s*Offset Sector: (\d+)\s*$")
    RE_SECTOR_SIZE = re.compile(r"^\s*Units are in (\d+)-byte sectors\s*$")

    @classmethod
    def from_str(
        cls, s: str, image_files: Iterable[str], imgtype: ImgType | None = None
    ) -> PartitionTable:
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
        part_table = cls(tuple(image_files), part_table_type, [], offset, sector_size, imgtype)
        for line in lines:
            try:
                part = Partition.from_str(line, part_table)
                part_table.partitions.append(part)
            except ValueError as e:
                LOGGER.debug(f"(Skipped line: {e})")
        return part_table

    def sectors_to_bytes(self, sectors: Sectors) -> int:
        return sectors * self.sector_size

    @cached_property
    def offset_bytes(self) -> int:
        return self.sectors_to_bytes(self.offset)

    @staticmethod
    def partlist_header() -> str:
        return (
            "ID : Slot     Start       (bytes)  End         (bytes)  "
            "Length      (bytes)  Description"
        )

    @cache
    def filesystem_partitions(self) -> list[Partition]:
        return [p for p in self.partitions if p.is_filesystem]

    def __str__(self) -> str:
        return (
            f"* Type: {self.part_table_type} [{self.part_table_type.value}]\n"
            f"* Offset: {self.offset} ({self.offset_bytes} B)\n"
            f"* Sector size: {self.sector_size} B\n"
            "* Partitions:\n"
            f"    {self.partlist_header()}\n"
        ) + "\n".join(f"  * {str(p)}" for p in self.partitions)

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
