#!/usr/bin/env python3

import sleuthlib


def main() -> None:
    mmls = sleuthlib.mmls(r"/home/mat/data-ntfs/2600/forensics_2/td_filesystems/disk3.001")
    print(mmls)


if __name__ == "__main__":
    main()
