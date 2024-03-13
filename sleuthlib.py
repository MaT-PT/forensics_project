from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NewType, TypeAlias

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


@dataclass
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

    @property
    def start_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.start)

    @property
    def end_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.end)

    @property
    def length_bytes(self) -> int:
        return self.partition_table.sectors_to_bytes(self.length)

    def __str__(self) -> str:
        return (
            f"{self.id:03}: {self.slot:7}  {self.start:>11} ({pretty_size(self.start_bytes):>5})  "
            f"{self.end:>11} ({pretty_size(self.end_bytes):>5})  {self.length:>11} "
            f"({pretty_size(self.length_bytes):>5})  {self.description}"
        )


@dataclass
class PartitionTable:
    part_table_type: PartTableType
    partitions: list[Partition]
    offset: Sectors = Sectors(0)
    sector_size: int = 512

    RE_OFFSET = re.compile(r"^\s*Offset Sector: (\d+)\s*$")
    RE_SECTOR_SIZE = re.compile(r"^\s*Units are in (\d+)-byte sectors\s*$")

    @classmethod
    def from_str(cls, s: str) -> PartitionTable:
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
        part_table = cls(part_table_type, [], offset, sector_size)
        for line in lines:
            try:
                part = Partition.from_str(line, part_table)
                part_table.partitions.append(part)
            except ValueError as e:
                print(f"(skipped line: {e})")
        return part_table

    def sectors_to_bytes(self, sectors: Sectors) -> int:
        return sectors * self.sector_size

    @property
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


def mmls(
    image_file: str,
    vstype: VsType | None = None,
    imgtype: ImgType | None = None,
    sector_size: int | None = None,
    offset: int | None = None,
) -> PartitionTable | None:
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
        print(res)
        return PartitionTable.from_str(res)
    except subprocess.CalledProcessError as e:
        print(f"Error running mmls: {e}")
        exit(e.returncode)
