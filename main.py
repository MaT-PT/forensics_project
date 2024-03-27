#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

from colorama import just_fix_windows_console
from termcolor import colored, cprint

from sleuthlib import check_required_tools, mmls, set_tsk_path
from sleuthlib.fls_types import FsEntryList
from sleuthlib.mmls_types import Partition, PartitionTable
from utils.argparse_utils import Arguments, parse_args
from utils.colored_logging import init_logging_colors, print_error, print_info, print_warning
from utils.config_parser import Config
from utils.filelist_parser import FileList

just_fix_windows_console()

logging.basicConfig(
    level=logging.WARNING,
    format=f"[%(asctime)s] %(levelname)s ({colored('%(name)s', 'grey', attrs=['bold'])}) "
    "%(message)s",
    # datefmt=f"%Y-%m-%d {colored('%H:%M:%S', attrs=['bold'])}",
    datefmt=f"{colored('%H:%M:%S', attrs=['bold'])}",
)
init_logging_colors()

SCRIPT_DIR = Path(__file__ if "__file__" in globals() else sys.argv[0]).parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"


def process_files(
    file_list: FileList,
    root_entries: FsEntryList,
    args: Arguments,
    out_dir: str | None = None,
    extra_vars: dict[str, str] = {},
) -> None:
    if out_dir is None:
        out_dir = args.out_dir

    for file in file_list:
        entries = root_entries.find_path(file.path)
        for entry in entries:
            if args.ls:
                print(entry.short_desc())
                continue

            if not args.silent:
                print_info(f"Extracting: {entry.short_desc()}")
            path: Path | None
            if entry.is_directory:
                path, _, _ = entry.save_dir(base_path=out_dir, parents=True)
            else:
                path, _ = entry.save_file(base_path=out_dir, parents=True)
            for tool in file.tools:
                if not args.silent:
                    print_info(f"Running {tool}")
                ret = tool.run(path, out_dir, extra_vars=extra_vars, silent=args.silent)
                if not args.silent and ret is None:
                    print_warning("Tool did not run (disabled or run_once)")
                if not (ret is None or args.silent or tool.output):
                    print()  # Add an empty line after each tool that ran


def process_partition(
    partition: Partition,
    part_num: int,
    file_list: FileList,
    args: Arguments,
    out_dir: str | None = None,
) -> None:
    if out_dir is None:
        out_dir = args.out_dir

    if not args.silent:
        print()
        if args.ls:
            print_info(f"Listing files in partition {part_num} ({partition.short_desc()})")
        else:
            print_info(f"Extracting partition {part_num} ({partition.short_desc()}) to '{out_dir}'")

    root_entries = partition.root_entries(case_insensitive=not args.case_sensitive)

    if args.save_all:
        root_entries.save_all(base_path=out_dir)
        return

    process_files(file_list, root_entries, args, out_dir, extra_vars={"PARTITION": str(part_num)})


def choose_partitions(partitions: list[Partition]) -> list[int]:
    default_part = max(enumerate(partitions), key=lambda i_p: i_p[1].length)[0]
    print("Please select the partition number(s) to use:")
    print()
    cprint(" NUM", "green", attrs=["bold"], end="")
    cprint(f" > {PartitionTable.partlist_header()}", attrs=["bold"])
    for num, part in enumerate(partitions):
        print(f"  {colored(f'{num:>2}', 'green', attrs=['bold'])} > {part}")
    print()
    try:
        user_input = input(
            "Partition number(s) (space- or comma-separated) "
            f"[{colored(default_part, 'green', attrs=['bold'])}]: "
        ).strip()
        print()
        if user_input == "":
            return [default_part]
        else:
            return [int(num) for num in user_input.replace(",", " ").split()]
    except ValueError:
        print_error("Invalid partition number")
        exit(1)


def main() -> None:
    args = parse_args()

    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif args.silent:
        logging.getLogger().setLevel(logging.ERROR)

    set_tsk_path(args.tsk_path)
    try:
        check_required_tools()
    except FileNotFoundError as e:
        print_error(str(e))
        exit(1)

    config = Config.from_yaml_file(CONFIG_FILE)
    file_list = FileList.empty(config)
    if args.file is not None:
        file_list.extend(args.file)
    if args.file_list is not None:
        for yaml_file in args.file_list:
            file_list += FileList.from_yaml_file(yaml_file, config)

    res_mmls = mmls(
        args.image,
        vstype=args.vstype,
        imgtype=args.imgtype,
        sector_size=args.sector_size,
        offset=args.offset,
    )
    if args.ls and not file_list:
        print(res_mmls)
        return

    partitions = res_mmls.filesystem_partitions()

    if args.part_num is None:
        if args.ask_part:
            if len(partitions) == 0:
                print_warning("No filesystem partitions found")
                return
            part_nums = choose_partitions(partitions)
        else:
            print_info("No partition specified, selecting all NTFS partitions...")
            part_nums = [i for i, part in enumerate(partitions) if part.is_ntfs]
    else:
        part_nums = args.part_num

    if not all(0 <= part_num < len(partitions) for part_num in part_nums):
        valid = "0"
        if len(partitions) > 1:
            valid += f"-{len(partitions) - 1}"
        print_error(
            f"Invalid partition number(s): {', '.join(str(part_num) for part_num in part_nums)} "
            f"(valid: {colored(valid, attrs=['bold'])})"
        )
        exit(1)

    if not args.silent:
        print_info("Selected partition(s):")
        for part_num in part_nums:
            print(f"    - {part_num}: {partitions[part_num].short_desc()}")

    if not file_list:
        if not args.silent:
            print_warning(f"No files to {'list' if args.ls else 'extract'}")
        return
    if not args.silent:
        print_info(f"Files to {'list' if args.ls else 'extract'}:")
        for file in file_list:
            print(f"    - {file.path}")

    out_dir_base = args.out_dir if args.out_dir is not None else "extracted"
    for part_num in part_nums:
        out_dir = f"{out_dir_base}_{part_num}" if len(part_nums) > 1 else out_dir_base
        process_partition(partitions[part_num], part_num, file_list, args, out_dir=out_dir)


if __name__ == "__main__":
    main()
