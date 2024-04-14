import pytest
import os
from sleuthlib.mmls_types import *
from sleuthlib.types import *


class TestMmlsTypes:

    def test_partition_table(self):
        
        # Basic checks, we change the sector size to 1024 instead of 512.
        # We also add an offset sector.
        partition_table_str = r'''
Offset Sector: 10
Units are in 1024-byte sectors

    Slot      Start        End          Length       Description
000:  Meta      0000000000   0000000000   0000000001   Safety Table
001:  -------   0000000000   0000002047   0000002048   Unallocated
002:  Meta      0000000001   0000000001   0000000001   GPT Header
003:  Meta      0000000002   0000000033   0000000032   Partition Table
004:  000       0000002048   0000206847   0000204800   EFI system partition
005:  001       0000206848   0000239615   0000032768   Microsoft reserved partition
006:  002       0000239616   0030417012   0030177397   Basic data partition
007:  -------   0030417013   0030418943   0000001931   Unallocated
008:  003       0030418944   0031453183   0001034240
009:  -------   0031453184   0031457279   0000004096   Unallocated
        '''

        table = PartitionTable.from_str(partition_table_str, [], None)

        assert table.sector_size == 1024
        assert table.sectors_to_bytes(Sectors(50)) == (50 * 1024)
        assert table.offset_bytes == 10 * 1024
        
        # Check filesystem partitions using start offset
        partition_table_str = r'''
Offset Sector: 0
Units are in 512-byte sectors

    Slot      Start        End          Length       Description
000:  Meta      0000000000   0000000000   0000000001   Safety Table
001:  -------   0000000000   0000002047   0000002048   Unallocated
002:  Meta      0000000001   0000000001   0000000001   GPT Header
003:  Meta      0000000002   0000000033   0000000032   Partition Table
004:  000       0000002048   0000206847   0000204800   EFI system partition
005:  001       0000206848   0000239615   0000032768   Microsoft reserved partition
006:  002       0000239616   0030417012   0030177397   Basic data partition
007:  -------   0030417013   0030418943   0000001931   Unallocated
008:  003       0030418944   0031453183   0001034240
009:  -------   0031453184   0031457279   0000004096   Unallocated
        '''

        table = PartitionTable.from_str(partition_table_str, [], None)
        assert table.filesystem_partitions()[0].start == Sectors(2048)
        assert table.filesystem_partitions()[1].start == Sectors(206848)
        assert table.filesystem_partitions()[2].start == Sectors(239616)
    
    def test_partitions(self):

        table = PartitionTable.from_str(r'''
Offset Sector: 0
Units are in 512-byte sectors

    Slot      Start        End          Length       Description
000:  Meta      0000000000   0000000000   0000000001   Safety Table
001:  -------   0000000000   0000002047   0000002048   Unallocated
002:  Meta      0000000001   0000000001   0000000001   GPT Header
003:  Meta      0000000002   0000000033   0000000032   Partition Table
004:  000       0000002048   0000206847   0000204800   EFI system partition
005:  001       0000206848   0000239615   0000032768   Microsoft reserved partition
006:  002       0000239616   0030417012   0030177397   Basic data partition
007:  -------   0030417013   0030418943   0000001931   Unallocated
008:  003       0030418944   0031453183   0001034240
009:  -------   0031453184   0031457279   0000004096   Unallocated       
        ''', [], None)

        partition = table.partitions[0]

        assert partition.description == "Safety Table"
        assert partition.id == 0
        assert partition.slot == "Meta"
        assert partition.start == Sectors(0)
        assert partition.end == Sectors(0)
        assert partition.length == Sectors(1)

        partition = table.partitions[5]

        assert partition.id == 5
        assert partition.slot == "001"
        assert partition.description == "Microsoft reserved partition"
        assert partition.start == Sectors(206848)
        assert partition.end == Sectors(239615)
        assert partition.length == Sectors(32768)
        assert partition.start_bytes == 206848 * 512
        assert partition.end_bytes == 239615 * 512
        assert partition.length_bytes == 32768 * 512
