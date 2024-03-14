from __future__ import annotations

import logging
import subprocess

from .mmls import Partition
from .types import MetaAddress

LOGGER = logging.getLogger(__name__)


def icat(partition: Partition, inode: MetaAddress) -> bytes:
    args: list[str] = []
    args.append("-r")  # Recover deleted files
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.extend(partition.partition_table.image_files)
    args.append(inode.address)

    try:
        LOGGER.debug(f"Running icat {' '.join(args)}")
        res = subprocess.check_output(["icat"] + args)
        LOGGER.debug(f"icat returned {len(res)} bytes")
        return res
    except subprocess.CalledProcessError as e:
        LOGGER.critical(f"Error running icat: {e}")
        exit(e.returncode)
