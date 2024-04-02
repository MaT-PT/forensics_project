import logging
from typing import Any

from .fls_types import FsEntry, FsEntryList
from .mmls_types import Partition
from .utils import run_program

LOGGER = logging.getLogger(__name__)


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
    args: list[str] = []
    # args += ["-p"]  # Show full path
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.extend(partition.partition_table.image_files)
    if root is not None:
        args.append(str(root.meta_address.address))

    res = run_program("fls", args, logger=LOGGER, encoding="utf-8", **kwargs)
    return FsEntryList(
        [FsEntry.from_str(line, partition, root, case_insensitive) for line in res.splitlines()]
    )
