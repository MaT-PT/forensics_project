import logging

from .mmls_types import Partition
from .types import MetaAddress
from .utils import run_program

LOGGER = logging.getLogger(__name__)


def icat(partition: Partition, inode: MetaAddress) -> bytes:
    args: list[str] = []
    args.append("-r")  # Recover deleted files
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.extend(partition.partition_table.image_files)
    args.append(inode.address)

    res = run_program("icat", args, logger=LOGGER)
    return res
