#!/usr/bin/env python3

import logging

from sleuthlib import mmls
from sleuthlib.utils import check_required_tools
from utils.argparse_utils import parse_args
from utils.parse_yaml import parse_yaml

logging.basicConfig(level=logging.INFO)


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.silent:
        logging.getLogger().setLevel(logging.CRITICAL)

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

    files = args.file or []
    for file_list in args.file_list or []:
        files.extend(parse_yaml(file_list))
    files = [f.replace("\\", "/").strip("/") for f in files]  # Normalize paths
    files = list(dict.fromkeys(files).keys())  # Remove duplicates

    if not args.silent:
        if not files:
            print("No files to extract")
            return
        print("Files to extract:")
        for file in files:
            print(f" - {file}")
        print()

    for file in files:
        entries = root_entries.find_path(file)
        for entry in entries:
            if not args.silent:
                print("Extracting:", entry)
            if entry.is_directory:
                entry.save_dir(base_path=args.out_dir, parents=True)
            else:
                entry.save_file(base_path=args.out_dir, parents=True)


if __name__ == "__main__":
    main()
