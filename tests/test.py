# To run this script, export 
import pytest
import shutil
import os
import subprocess
import shlex


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
MAIN_PATH = os.path.join(DIR_PATH, "../main.py")
FILES_PATH = os.environ.get("FILES_PATH")
DISKE01_PATH = os.path.join(FILES_PATH if FILES_PATH else "", "disk.E01")
ASSETS = os.path.join(DIR_PATH, "..", "assets")

if not FILES_PATH:
    pytest.skip("Please set FILES_PATH environment variable with path of directory which contain test image.", allow_module_level=True)
    
def run_main(cmd):
    args = shlex.split("%s %s" % (MAIN_PATH, cmd))
    proc = subprocess.run(args, check=True, text=True, capture_output=True)
    return proc.stdout


def test_check_requirements():

    # Basic checks
    assert FILES_PATH != None
    assert os.path.isdir(FILES_PATH)
    assert os.path.isfile(DISKE01_PATH)


def test_list_partitions():

    stdout = run_main("%s -l" % (DISKE01_PATH))
    assert stdout == r'''Type: GUID Partition Table (EFI) [gpt]
Offset: 0 (0 B)
Sector size: 512 B
Partitions:
   ID : Slot           Start (bytes)          End (bytes)       Length (bytes)  Description
 * 000: Meta               0 (   0B)            0 (   0B)            1 ( 512B)  Safety Table
 * 001: -------            0 (   0B)         2047 (1023K)         2048 (   1M)  Unallocated
 * 002: Meta               1 ( 512B)            1 ( 512B)            1 ( 512B)  GPT Header
 * 003: Meta               2 (   1K)           33 (  16K)           32 (  16K)  Partition Table
 * 004: 000             2048 (   1M)       411647 ( 200M)       409600 ( 200M)  EFI system partition
 * 005: 001           411648 ( 201M)       673791 ( 328M)       262144 ( 128M)  Microsoft reserved partition
 * 006: 002           673792 ( 329M)    125827071 (  59G)    125153280 (  59G)  Basic data partition
 * 007: -------    125827072 (  59G)    125829119 (  59G)         2048 (   1M)  Unallocated
'''

def test_extract_files(tmpdir):

    # Test for existing files with wildcard
    FILES_TO_CHECK = [
        os.path.join(tmpdir, "Users", "Laurent", "NTUSER.DAT"),
        os.path.join(tmpdir, "Users", "Default", "NTUSER.DAT"),
    ]

    run_main("%s -d %s -p 2 -f \"Users/*/NTUSER.DAT\"" % (DISKE01_PATH, tmpdir))    
    for file in FILES_TO_CHECK:
        assert os.path.isfile(file)

    # Test for non existing file
    run_main("%s -d %s -p 2 -f \"Users/Default/unknow.txt\"" % (DISKE01_PATH, tmpdir))
    assert not os.path.exists(os.path.join(tmpdir, "Users", "Default", "unknow.txt"))



def test_extract_files_from_yaml(tmpdir):

    DIR1 = os.path.join(tmpdir, "1")
    FILES1 = os.path.join(ASSETS, "files1.yaml")
    DIR2 = os.path.join(tmpdir, "2")
    FILES2 = os.path.join(ASSETS, "files2.yaml")

    os.mkdir(DIR1)
    os.mkdir(DIR2)

    run_main("%s -d %s -p 2 -F %s" % (DISKE01_PATH, DIR1, FILES1))
    assert os.path.exists(os.path.join(DIR1, "Users", "Default", "NTUSER.DAT.LOG1"))
    assert os.path.exists(os.path.join(DIR1, "Users", "Default", "NTUSER.DAT"))
    assert os.path.exists(os.path.join(DIR1, "Users", "Laurent", "NTUSER.DAT"))
    assert not os.path.exists(os.path.join(DIR1, "Users", "Laurent", "unnkow.txt"))
    
    run_main("%s -d %s -p 2 -F %s" % (DISKE01_PATH, DIR2, FILES2))
    assert os.path.exists(os.path.join(DIR2, "Users", "Default", "NTUSER.DAT.LOG1"))
    assert os.path.exists(os.path.join(DIR2, "Users", "Default", "NTUSER.DAT"))
    assert os.path.exists(os.path.join(DIR2, "Users", "Laurent", "NTUSER.DAT"))
    assert not os.path.exists(os.path.join(DIR2, "Users", "Laurent", "unnkow.txt"))


def test_evtx_dump(tmpdir):
    
    assert shutil.which("evtx_dump") != None

    FILES3 = os.path.join(ASSETS, "files3.yaml")
    CONFIG3 = os.path.join(ASSETS, "config3.yaml")

    run_main("%s -d %s -p 2 -F %s -c %s" % (DISKE01_PATH, tmpdir, FILES3, CONFIG3))

    assert os.path.exists(os.path.join(tmpdir, "_evtx_dump"))
    assert os.path.exists(os.path.join(tmpdir, "_evtx_dump", "System.evtx.xml"))
