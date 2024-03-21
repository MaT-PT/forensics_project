#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

from sleuthlib import mmls
from sleuthlib.utils import check_required_tools
from utils.argparse_utils import parse_args
from utils.config_parser import Config
from utils.filelist_parser import FileList

logging.basicConfig(level=logging.WARNING)

SCRIPT_DIR = Path(__file__ if "__file__" in globals() else sys.argv[0]).parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"


def main() -> None:
    args = parse_args()

    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif args.silent:
        logging.getLogger().setLevel(logging.ERROR)

    try:
        check_required_tools(args.tsk_path)
    except FileNotFoundError as e:
        print("Error:", e)
        exit(1)

    res_mmls = mmls(
        args.image,
        vstype=args.vstype,
        imgtype=args.imgtype,
        sector_size=args.sector_size,
        offset=args.offset,
    )
    if args.list_parts or not (args.file or args.file_list or args.save_all):
        print(res_mmls)
        return

    partitions = res_mmls.filesystem_partitions()

    if args.part_num is None:
        if len(partitions) == 0:
            print("No filesystem partitions found")
            return
        default_part = max(enumerate(partitions), key=lambda i_p: i_p[1].length)[0]
        print("Please select a partition number:")
        print()
        print(f" NUM > {res_mmls.partlist_header()}")
        for num, part in enumerate(partitions):
            print(f"  {num:>2} > {part}")
        print()
        try:
            part_num = int(input(f"Partition number [{default_part}]: ") or default_part)
        except ValueError:
            print("Invalid partition number")
            exit(1)
    else:
        part_num = args.part_num

    if not 0 <= part_num < len(partitions):
        valid = "0"
        if len(partitions) > 1:
            valid += f"-{len(partitions) - 1}"
        print(f"Invalid partition number: {part_num} (valid: {valid})")
        exit(1)
    partition = partitions[part_num]
    if not args.silent:
        print(f"Selected partition: {partition.short_desc()}")
        print()

    root_entries = partition.root_entries(case_insensitive=not args.case_sensitive)

    if args.save_all:
        root_entries.save_all(base_path=args.out_dir)
        return

    config = Config.from_yaml_file(CONFIG_FILE)
    file_list = FileList.empty(config)
    if args.file is not None:
        file_list.extend(args.file)
    if args.file_list is not None:
        for yaml_file in args.file_list:
            file_list += FileList.from_yaml_file(yaml_file, config)

    if not args.silent:
        if not file_list:
            print("No files to extract")
            return
        print("Files to extract:")
        for file in file_list:
            print(f" - {file.path}")
        print()

    for file in file_list:
        entries = root_entries.find_path(file.path)
        for entry in entries:
            if not args.silent:
                print("Extracting:", entry)
            path: Path | None
            if entry.is_directory:
                path, _, _ = entry.save_dir(base_path=args.out_dir, parents=True)
            else:
                path, _ = entry.save_file(base_path=args.out_dir, parents=True)
            for tool in file.tools:
                tool.run(path, args.out_dir, silent=args.silent, check=True)
                if not args.silent:
                    print()  # Add an empty line after each tool


if __name__ == "__main__":
    main()
