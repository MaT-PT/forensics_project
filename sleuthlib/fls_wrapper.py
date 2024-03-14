from __future__ import annotations

import logging
import subprocess

from .fls_types import FsEntry, FsEntryList
from .mmls_types import Partition

LOGGER = logging.getLogger(__name__)


def fls(
    partition: Partition, root: FsEntry | None = None, case_insensitive: bool = False
) -> FsEntryList:
    args: list[str] = []
    # args += ["-p"]  # Show full path
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.extend(partition.partition_table.image_files)
    if root is not None:
        args.append(str(root.meta_address.address))

    try:
        LOGGER.debug(f"Running fls {' '.join(args)}")
        res = subprocess.check_output(["fls"] + args, encoding="utf-8")
        LOGGER.debug(f"fls returned: {res}")
        return FsEntryList(
            [FsEntry.from_str(line, partition, root, case_insensitive) for line in res.splitlines()]
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running fls: {e}")
        exit(e.returncode)
