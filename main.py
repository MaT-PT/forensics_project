#!/usr/bin/env python3

import argparse

from argparse_utils import ListableAction, int_min
from sleuthlib import fls, mmls
from sleuthlib.types import IMG_TYPES, PART_TABLE_TYPES


def main() -> None:
    parser = argparse.ArgumentParser(description="TheSleuthKit Python Interface")
    # TODO: Add support for multiple images
    # parser.add_argument("image", nargs="+", help="The image(s) to analyze")
    parser.add_argument("image", help="The image(s) to analyze")
    parser.add_argument(
        "-t",
        action=ListableAction,
        choices=PART_TABLE_TYPES,
        help="The type of volume system (use '-t list' to list supported types)",
        metavar="vstype",
    )
    parser.add_argument(
        "-i",
        action=ListableAction,
        choices=IMG_TYPES,
        help="The format of the image file (use '-i list' to list supported types)",
        metavar="imgtype",
    )
    parser.add_argument(
        "-b",
        type=int_min(512),
        help="The size (in bytes) of the device sectors",
        metavar="dev_sector_size",
    )
    parser.add_argument(
        "-o",
        type=int_min(0),
        help="Offset to the start of the volume that contains the partition system (in sectors)",
        metavar="imgoffset",
    )

    args = parser.parse_args()
    res_mmls = mmls(
        args.image,
        vstype=args.t,
        imgtype=args.i,
        sector_size=args.b,
        offset=args.o,
    )
    print(res_mmls)

    partition = max(res_mmls.partitions, key=lambda p: p.length)
    print(f"Selected partition: {partition}")
    res_fls = fls(partition, case_insensitive=True)
    for f in res_fls:
        print(f)
    print()
    windows = res_fls["Windows"]
    for f in windows.children():
        print(f)
    print()
    system32 = windows.child("System32")
    for f in system32.children():
        print(f)

    print()
    config = res_fls.find_path("Windows/System32/config")
    print("Config with find_path:", config)

    config = windows.child_path("System32/config")
    print("Config with child_path:", config)

    reg_system = config.child("SYSTEM")
    print("System registry:", reg_system)
    filepath, written = reg_system.save()
    print(f"Written {written} bytes to '{filepath}'")
    with open("SYSTEM2", "wb") as file:
        filepath, written = reg_system.save(file)
        print(f"Written {written} bytes to '{filepath}'")

    try:
        data = config.extract_file()
        print("config data:", data)
    except ValueError as e:
        print(f"Expected error: {e}")

    dirpath, nfiles, ndirs = res_fls.find_path("Windows/System32/drivers/etc").save_dir()
    print(f"Saved {nfiles} files and {ndirs} directories to '{dirpath}'")


if __name__ == "__main__":
    main()
