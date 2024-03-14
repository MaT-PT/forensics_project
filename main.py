#!/usr/bin/env python3

import argparse
import logging

from argparse_utils import ListableAction, int_min
from sleuthlib import fls, mmls
from sleuthlib.types import IMG_TYPES, PART_TABLE_TYPES

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="TheSleuthKit Python Interface")
    parser.add_argument("image", nargs="+", help="The image(s) to analyze")
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
        "--sector_size",
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
        "--list",
        "-l",
        action="store_true",
        help="List the partitions and exit (default if no file is specified)",
    )
    parser.add_argument(
        "--part-num",
        "-p",
        type=int_min(0),
        help="The partition number (slot) to use",
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
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.silent:
        logging.getLogger().setLevel(logging.CRITICAL)

    res_mmls = mmls(
        args.image,
        vstype=args.vstype,
        imgtype=args.imgtype,
        sector_size=args.sector_size,
        offset=args.offset,
    )
    if args.list or not (args.file or args.file_list):
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

    if part_num < 0 or part_num >= len(partitions):
        print(f"Invalid partition number: {part_num} (valid: 0-{len(partitions) - 1})")
        exit(1)
    partition = partitions[part_num]
    if not args.silent:
        print(f"Selected partition: {partition.short_desc()}")
        print()

    res_fls = fls(partition, case_insensitive=not args.case_sensitive)
    files = args.file or []
    for file in files:
        entry = res_fls.find_path(file)
        if entry.is_directory:
            entry.save_dir(base_path=args.out_dir, subdir=True)
        else:
            entry.save_file(base_path=args.out_dir)


if __name__ == "__main__":
    main()
