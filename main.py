#!/usr/bin/env python3

import argparse

import sleuthlib
from argparse_utils import ListableAction, int_min


def main() -> None:
    parser = argparse.ArgumentParser(description="TheSleuthKit Python Interface")
    # TODO: Add support for multiple images
    # parser.add_argument("image", nargs="+", help="The image(s) to analyze")
    parser.add_argument("image", help="The image(s) to analyze")
    parser.add_argument(
        "-t",
        action=ListableAction,
        choices=sleuthlib.PART_TABLE_TYPES,
        help="The type of volume system (use '-t list' to list supported types)",
        metavar="vstype",
    )
    parser.add_argument(
        "-i",
        action=ListableAction,
        choices=sleuthlib.IMG_TYPES,
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
    mmls = sleuthlib.mmls(
        args.image,
        vstype=args.t,
        imgtype=args.i,
        sector_size=args.b,
        offset=args.o,
    )
    print(mmls)

    partition = max(mmls.partitions, key=lambda p: p.length)
    print(f"Selected partition: {partition}")
    fls = sleuthlib.fls(partition, case_insensitive=True)
    for f in fls:
        print(f)
    print()
    windows = fls["Windows"]
    for f in windows.children():
        print(f)
    print()
    system32 = windows.child("System32")
    for f in system32.children():
        print(f)


if __name__ == "__main__":
    main()
