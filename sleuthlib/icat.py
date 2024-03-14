from __future__ import annotations

import subprocess

from .mmls import Partition
from .types import MetaAddress


def icat(partition: Partition, inode: MetaAddress) -> bytes:
    args: list[str] = []
    args.append("-r")  # Recover deleted files
    args += ["-o", str(partition.start)]  # Image offset
    if partition.partition_table.img_type is not None:
        args += ["-i", partition.partition_table.img_type]  # Image type
    args.append(partition.partition_table.image_file)
    args.append(inode.address)

    try:
        return subprocess.check_output(["icat"] + args)
    except subprocess.CalledProcessError as e:
        print(f"Error running fls: {e}")
        exit(e.returncode)
