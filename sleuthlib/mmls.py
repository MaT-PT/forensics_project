from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import cached_property
from typing import Iterable

from .types import ImgType, PartTableType, Sectors, VsType
from .utils import pretty_size


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


def mmls(
    image_files: str | Iterable[str],
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
    if isinstance(image_files, str):
        image_files = (image_files,)
    args.extend(image_files)

    try:
        res = subprocess.check_output(["mmls"] + args, encoding="utf-8")
        # print(res)
        return PartitionTable.from_str(res, image_file, imgtype)
    except subprocess.CalledProcessError as e:
        print(f"Error running mmls: {e}")
        exit(e.returncode)
