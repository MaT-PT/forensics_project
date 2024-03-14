from __future__ import annotations

import logging
import subprocess
from typing import Iterable

from .mmls_types import PartitionTable
from .types import ImgType, VsType

LOGGER = logging.getLogger(__name__)


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
        LOGGER.debug(f"Running mmls {' '.join(args)}")
        res = subprocess.check_output(["mmls"] + args, encoding="utf-8")
        LOGGER.debug(f"mmls returned: {res}")
        return PartitionTable.from_str(res, image_files, imgtype)
    except subprocess.CalledProcessError as e:
        print(f"Error running mmls: {e}")
        exit(e.returncode)
