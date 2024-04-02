import logging
from typing import Any, Iterable

from .mmls_types import PartitionTable
from .types import ImgType, VsType
from .utils import run_program

LOGGER = logging.getLogger(__name__)


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

    res = run_program("mmls", args, logger=LOGGER, encoding="utf-8", **kwargs)
    return PartitionTable.from_str(res, image_files, imgtype)
