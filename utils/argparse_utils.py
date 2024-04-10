from argparse import Action, ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Sequence, TypeVar

from sleuthlib.types import IMG_TYPES, PART_TABLE_TYPES, ImgType, Sectors, VsType

_T = TypeVar("_T")


@dataclass(frozen=True)
class Arguments:
    """Parsed, typed arguments from the CLI."""

    image: list[str]
    tsk_path: str | None
    vstype: VsType | None
    imgtype: ImgType | None
    sector_size: int | None
    offset: Sectors | None
    part_num: list[int] | None
    ask_part: bool
    ls: bool
    save_all: bool
    file: list[str] | None
    file_list: list[str] | None
    out_dir: str | None
    config: str | None
    case_sensitive: bool
    silent: bool
    verbose: int


class ListableAction(Action):
    """Argparse action that shows the supported choices for an argument if the value is `list`."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: int | Literal["?", "*", "+"] | None = None,
        default: _T | None = None,
        type: Callable[[str], _T] | None = None,
        choices: Mapping[str, str] | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ) -> None:
        if choices is None or not isinstance(choices, Mapping):
            raise ValueError("choices must be a mapping of option names -> descriptions")
        super(ListableAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            default=default,
            type=type,
            choices=set(choices.keys()) | {"list"},
            required=required,
            help=help,
            metavar=metavar,
        )
        self._choices_map = choices

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        setattr(namespace, self.dest, values)
        if values is None:
            values = []
        elif isinstance(values, str):
            values = [values]
        if "list" in values:
            print(f"Supported choices for {self.metavar or self.dest}:")
            for k, v in self._choices_map.items():
                print(f"  {k}: {v}")
            parser.exit()


def int_min(min_val: int = 0) -> Callable[[str], int]:
    """Returns a function that converts a string to an integer, ensuring its value is >= min_val."""

    def int_min_inner(value: str) -> int:
        try:
            n = int(value)
        except ValueError as e:
            raise ArgumentTypeError(str(e))
        if n < min_val:
            raise ArgumentTypeError(f"should be an integer >= {min_val}")
        return n

    return int_min_inner


def parse_args() -> Arguments:
    """Parses the CLI arguments using argparse, and returns them as a typed dataclass."""
    parser = ArgumentParser(description="'The Sleuth Kit' Python Interface")
    parser.add_argument(
        "image", nargs="+", help="The image file(s) to analyze (if multiple, concatenate them)"
    )

    grp_tsk = parser.add_argument_group("The Sleuth Kit options")
    grp_tsk.add_argument(
        "-T",
        "--tsk-path",
        help="The directory where the TSK tools are installed (default: search in PATH)",
    )
    grp_tsk.add_argument(
        "-t",
        "--vstype",
        action=ListableAction,
        choices=PART_TABLE_TYPES,
        help="The type of volume system (use '-t list' to list supported types)",
    )
    grp_tsk.add_argument(
        "-i",
        "--imgtype",
        action=ListableAction,
        choices=IMG_TYPES,
        help="The format of the image file (use '-i list' to list supported types)",
    )
    grp_tsk.add_argument(
        "-b",
        "--sector-size",
        type=int_min(512),
        help="The size (in bytes) of the device sectors",
    )
    grp_tsk.add_argument(
        "-o",
        "--offset",
        type=int_min(0),
        help="Offset to the start of the volume that contains the partition system (in sectors)",
    )

    grp_extract = parser.add_argument_group("Extraction options")
    xgrp_partition = grp_extract.add_mutually_exclusive_group()
    xgrp_partition.add_argument(
        "-p",
        "--part-num",
        action="extend",
        nargs="+",
        type=int_min(0),
        help="The partition number(s) (slots) to use (if not specified, use all NTFS partitions)",
    )
    xgrp_partition.add_argument(
        "-P",
        "--ask-part",
        action="store_true",
        help="List data partitions and ask for which one(s) to use",
    )
    xgrp_list_save = grp_extract.add_mutually_exclusive_group()
    xgrp_list_save.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="ls",
        help="If no file is specified, list all partitions; otherwise, list the given files",
    )
    xgrp_list_save.add_argument(
        "-a",
        "--save-all",
        action="store_true",
        help="Save all files and directories in the partition",
    )
    grp_extract.add_argument(
        "-f",
        "--file",
        action="extend",
        nargs="+",
        help="The file(s)/dir(s) to extract",
    )
    grp_extract.add_argument(
        "-F",
        "--file-list",
        action="extend",
        nargs="+",
        help="YAML file(s) containing the file(s)/dir(s) to extract, with tools to use and options",
    )
    grp_extract.add_argument(
        "-d",
        "--out-dir",
        help="The directory to extract the file(s)/dir(s) to",
    )
    grp_extract.add_argument(
        "-c",
        "--config",
        help="The YAML file containing the configuration of the tools to use and directories",
    )
    grp_extract.add_argument(
        "-S",
        "--case-sensitive",
        action="store_true",
        help="Case-sensitive file search (default is case-insensitive)",
    )

    xgrp_verbosity = parser.add_mutually_exclusive_group()
    xgrp_verbosity.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="Suppress output",
    )
    xgrp_verbosity.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbose output (use multiple times for more verbosity)",
    )

    args = parser.parse_args()

    if args.save_all and (args.file or args.file_list):
        parser.error("cannot specify --save-all and --file/--file-list at the same time")

    if args.part_num is not None:
        # Remove duplicates while preserving order
        args.part_num = list(dict.fromkeys(args.part_num).keys())

    return Arguments(**args.__dict__)
