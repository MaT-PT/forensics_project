from typing import Any, Iterable

from .fls_types import FsEntry, FsEntryList
from .icat_wrapper import icat
from .mmls_types import Partition, PartitionTable
from .types import ImgType, VsType
from .utils import check_required_tools, set_tsk_path

__all__ = [
    "mmls",
    "fls",
    "icat",
    "check_required_tools",
    "set_tsk_path",
    "Partition",
    "PartitionTable",
    "FsEntry",
    "FsEntryList",
]


def mmls(
    image_files: str | Iterable[str],
    vstype: VsType | None = None,
    imgtype: ImgType | None = None,
    sector_size: int | None = None,
    offset: int | None = None,
    **kwargs: Any,
) -> PartitionTable:
    """Runs the `mmls` tool to extract partition information from an image.

    Args:
        image_files: Path to the image file(s).
        vstype: Volume system type to use (`dos`, `mac`, `bsd`, `sun`, or `gpt`).
        imgtype: Image type to use (`raw`, `aff`, `afd`, `afm`, `afflib`, `ewf`, `vmdk`, or `vhd`).
        sector_size: Sector size to use.
        offset: Offset to use for the start of the volume.
        **kwargs: Additional arguments to pass to `run_program`.
    """
    return PartitionTable.from_image_files(
        image_files, vstype, imgtype, sector_size, offset, **kwargs
    )


def fls(
    partition: Partition, root: FsEntry | None = None, case_insensitive: bool = False, **kwargs: Any
) -> FsEntryList:
    """Runs the `fls` tool to list files in a partition.

    Args:
        partition: The partition to list files from.
        root: The root entry to list files from.
        case_insensitive: Whether to use case-insensitive matching (for FAT/NFTS partitions)
        **kwargs: Additional arguments to pass to `run_program`.
    """
    return FsEntryList.from_partition(partition, root, case_insensitive, **kwargs)
