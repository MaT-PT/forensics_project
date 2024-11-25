import logging
from typing import Any

from .mmls_types import Partition
from .types import MetaAddress
from .utils import run_program

LOGGER = logging.getLogger(__name__)


def icat(partition: Partition, inode: MetaAddress, **kwargs: Any) -> bytes:
    """Runs the `icat` tool to extract a file from a partition.

    Args:
        partition: The partition to extract the file from.
        inode: The inode to extract.
        **kwargs: Additional arguments to pass to `run_program`."""
    args: list[str] = []
    args.append("-r")  # Recover deleted files
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.extend(partition.partition_table.image_files)
    args.append(inode.address)

    res = run_program("icat", args, logger=LOGGER, encoding=None, **kwargs)
    return res
