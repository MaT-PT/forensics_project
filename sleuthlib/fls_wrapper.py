import logging

from .fls_types import FsEntry, FsEntryList
from .mmls_types import Partition
from .utils import run_program

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

    res = run_program("fls", args, logger=LOGGER, encoding="utf-8")
    return FsEntryList(
        [FsEntry.from_str(line, partition, root, case_insensitive) for line in res.splitlines()]
    )
