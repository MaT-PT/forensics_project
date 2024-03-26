from argparse import Action, ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Sequence, TypeVar

from sleuthlib.types import IMG_TYPES, PART_TABLE_TYPES, ImgType, Sectors, VsType

_T = TypeVar("_T")


@dataclass(frozen=True)
class Arguments:
    image: list[str]
    tsk_path: str | None
    vstype: VsType | None
    imgtype: ImgType | None
    sector_size: int | None
    offset: Sectors | None
    ls: bool
    part_num: int | None
    file: list[str] | None
    file_list: list[str] | None
    save_all: bool
    out_dir: str | None
    case_sensitive: bool
    silent: bool
    verbose: int


def int_min(min_val: int = 0) -> Callable[[str], int]:
    def int_min_inner(value: str) -> int:
        try:
            n = int(value)
        except ValueError as e:
            raise ArgumentTypeError(str(e))
        if n < min_val:
            raise ArgumentTypeError(f"should be an integer >= {min_val}")
        return n

    return int_min_inner


class ListableAction(Action):
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


def parse_args() -> Arguments:
    parser = ArgumentParser(description="TheSleuthKit Python Interface")
    parser.add_argument("image", nargs="+", help="The image(s) to analyze")
    parser.add_argument(
        "--tsk-path",
        "-T",
        help="The directory where the TSK tools are installed (default: search in PATH)",
    )
    parser.add_argument(
        "--vstype",
        "-t",
        action=ListableAction,
        choices=PART_TABLE_TYPES,
        help="The type of volume system (use '-t list' to list supported types)",
    )
    parser.add_argument(
        "--imgtype",
        "-i",
        action=ListableAction,
        choices=IMG_TYPES,
        help="The format of the image file (use '-i list' to list supported types)",
    )
    parser.add_argument(
        "--sector-size",
        "-b",
        type=int_min(512),
        help="The size (in bytes) of the device sectors",
    )
    parser.add_argument(
        "--offset",
        "-o",
        type=int_min(0),
        help="Offset to the start of the volume that contains the partition system (in sectors)",
    )
    parser.add_argument(
        "--part-num",
        "-p",
        type=int_min(0),
        help="The partition number (slot) to use",
    )
    xgrp_list_save = parser.add_mutually_exclusive_group()
    xgrp_list_save.add_argument(
        "--list",
        "-l",
        action="store_true",
        dest="ls",
        help="If no file is specified, list the partitions; otherwise, list the given files",
    )
    xgrp_list_save.add_argument(
        "--save-all",
        "-a",
        action="store_true",
        help="Save all files and directories in the partition",
    )
    parser.add_argument(
        "--file",
        "-f",
        action="extend",
        nargs="+",
        help="The file(s)/dir(s) to extract",
    )
    parser.add_argument(
        "--file-list",
        "-F",
        action="extend",
        nargs="+",
        help="YAML file(s) containing the file(s)/dir(s) to extract",
    )
    parser.add_argument(
        "--out-dir",
        "-d",
        help="The directory to extract the file(s)/dir(s) to",
    )
    parser.add_argument(
        "--case-sensitive",
        "-S",
        action="store_true",
        help="Case-sensitive file search (default is case-insensitive)",
    )
    xgrp_verbosity = parser.add_mutually_exclusive_group()
    xgrp_verbosity.add_argument(
        "--silent",
        "-s",
        action="store_true",
        help="Suppress output",
    )
    xgrp_verbosity.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Verbose output (use multiple times for more verbosity)",
    )

    args = parser.parse_args()

    if args.save_all and (args.file or args.file_list):
        parser.error("cannot specify --save-all and --file/--file-list at the same time")

    return Arguments(**args.__dict__)
