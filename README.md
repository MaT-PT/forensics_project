# Forensics Project 2600

## Description

This is an automated forensic analysis tool that can be used to extract files and directories from a disk image and run customized tools on them after extraction. All configuration is done through YAML files.

It is written in Python and uses *The Sleuth Kit* (TSK) behind the scenes. It can run on Windows, Linux, and MacOS.

This tool was written using TSK version 4.12.1.

## Table of contents <!-- omit in toc -->

- [Forensics Project 2600](#forensics-project-2600)
  - [Description](#description)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Breaking down the options](#breaking-down-the-options)
    - [Examples](#examples)
  - [YAML files](#yaml-files)
    - [Configuration file](#configuration-file)
      - [Structure](#structure)
      - [Included tools](#included-tools)
      - [Examples](#examples-1)
    - [File list](#file-list)
      - [Structure](#structure-1)
      - [Examples](#examples-2)
    - [Variables](#variables)

## Installation

1. Install or download *The Sleuth Kit* (TSK)
    - **Windows**: Download it from [https://www.sleuthkit.org/sleuthkit/download.php](https://www.sleuthkit.org/sleuthkit/download.php)
    - **Linux**: Use your package manager to install it. For example, on Debian/Ubuntu: `sudo apt install sleuthkit` (alternatively, you can compile it from source)
    - **MacOS**: Use Homebrew to install it: `brew install sleuthkit`
2. Install Python 3
3. Clone this repository
4. Install the required Python packages: `pip install -r requirements.txt` (or `pip install -r requirements-dev.txt` if you want to contribute to the project)
5. Install or download the required binaries for tools (eg. `regripper`, `srum-dump`, `evtx_dump`, etc.) that you want to run on the extracted files
    - Make sure the paths to the tool binaries are correctly set in the config file (see below)
6. Run the tool:
    - **Windows**: `python3 main.py [image_file] [options]` (or `py main.py [image_file] [options]` depending on your Python installation)
    - **Linux/MacOS**: `./main.py [image_file] [options]`

## Usage

<details>
  <summary><code>./main.py --help</code></summary>

```text
usage: main.py [-h] [-T TSK_PATH] [-t {bsd,mac,list,gpt,dos,sun}]
               [-i {afm,list,vhd,vmdk,aff,afflib,ewf,afd,raw}] [-b SECTOR_SIZE] [-o OFFSET]
               [-p PART_NUM [PART_NUM ...] | -P] [-l | -a] [-f FILE [FILE ...]]
               [-F FILE_LIST [FILE_LIST ...]] [-d OUT_DIR] [-c CONFIG] [-S] [-s | -v]
               image [image ...]

'The Sleuth Kit' Python Interface

positional arguments:
  image                 The image file(s) to analyze (if multiple, concatenate them)

options:
  -h, --help            show this help message and exit
  -s, --silent          Suppress output
  -v, --verbose         Verbose output (use multiple times for more verbosity)

The Sleuth Kit options:
  -T TSK_PATH, --tsk-path TSK_PATH
                        The directory where the TSK tools are installed (default: search in PATH)
  -t {bsd,mac,list,gpt,dos,sun}, --vstype {bsd,mac,list,gpt,dos,sun}
                        The type of volume system (use '-t list' to list supported types)
  -i {afm,list,vhd,vmdk,aff,afflib,ewf,afd,raw}, --imgtype {afm,list,vhd,vmdk,aff,afflib,ewf,afd,raw}
                        The format of the image file (use '-i list' to list supported types)
  -b SECTOR_SIZE, --sector-size SECTOR_SIZE
                        The size (in bytes) of the device sectors
  -o OFFSET, --offset OFFSET
                        Offset to the start of the volume that contains the partition system (in sectors)

Extraction options:
  -p PART_NUM [PART_NUM ...], --part-num PART_NUM [PART_NUM ...]
                        The partition number(s) (slots) to use (if not specified, use all NTFS partitions)
  -P, --ask-part        List data partitions and ask for which one(s) to use
  -l, --list            If no file is specified, list all partitions; otherwise, list the given files
  -a, --save-all        Save all files and directories in the partition
  -f FILE [FILE ...], --file FILE [FILE ...]
                        The file(s)/dir(s) to extract
  -F FILE_LIST [FILE_LIST ...], --file-list FILE_LIST [FILE_LIST ...]
                        YAML file(s) containing the file(s)/dir(s) to extract, with tools to use and options
  -d OUT_DIR, --out-dir OUT_DIR
                        The directory to extract the file(s)/dir(s) to
  -c CONFIG, --config CONFIG
                        The YAML file containing the configuration of the tools to use and directories
  -S, --case-sensitive  Case-sensitive file search (default is case-insensitive)
```

</details>

### Breaking down the options

> Note: For all options that can take multiple values (`-p`, `-f`, `-F`), you can specify them multiple times, or separate them with spaces (eg. `-p 1 -p 2 -p 3` or `-p 1 2 3`). The same goes for `-v` (eg. `-v -v` or `-vv`).

- Positional arguments:
  - `image`: One or more image file(s) to analyze. They are passed as-is to the TSK tools, so they can be in any supported format (eg. raw, EWF, VMDK, etc.). Specifying multiple files is only useful for split images (eg. `image.E01, image.E02, …`). Doing so for different images is not supported and will NOT allow you to extract files from multiple images at once. TSK will try to detect the other parts of a split image automatically if they end with sequential numbers (eg. `.E01, .E02, …`, `.001, .002, …`).

- General options:
  - `-h, --help`: Show the help message and exit.
  - `-s, --silent`: Suppress informative output from script and STDOUT from tools (warnings/errors and STDERR will still be printed).
  - `-v, --verbose`: Verbose output (use once for INFO level messages, twice for DEBUG level).

- Options related to TSK:
  - `-T, --tsk-path`: The directory where the TSK binaries are installed. If not specified, the script will search for them in the PATH.
  - The following options are the same as the ones in the TSK tools (you most likely won't need to change them as TSK will automatically choose the correct values):
    - `-t, --vstype`: The type of volume system. Use `-t list` to list the supported types (`dos`, `mac`, `bsd`, `sun`, `gpt`).
    - `-i, --imgtype`: The format of the image file. Use `-i list` to list the supported types (`raw`, `aff`, `afd`, `afm`, `afflib`, `ewf`, `vmdk`, `vhd`, `logical`).
    - `-b, --sector-size`: The size (in bytes) of the device sectors (multiple of 512).
    - `-o, --offset`: Offset to the start of the volume that contains the partition system (in sectors).

- Options for extraction:
  - `-p, --part-num`: The partition number(s) (slots) to use. If not specified, all NTFS partitions will be used (exclusive with `-P`).
  - `-P, --ask-part`: List data partitions and ask for which one(s) to use (exclusive with `-p`).
  - `-l, --list`: If no file or file list is specified, list all partitions; otherwise, list the given files (exclusive with `-a`).
  - `-a, --save-all`: Save all files and directories in the partition, do not run any tool (exclusive with `-l`).
  - `-f, --file`: The file(s)/dir(s) to extract (no tools will be run on them).
  - `-F, --file-list`: YAML file(s) containing the file(s)/dir(s) to extract, with tools to use and options (see below for more information).
  - `-d, --out-dir`: The directory to extract the file(s)/dir(s) to (default is `extracted`). If several partitions are extracted, their number will be appended to the directory name with an underscore.
  - `-c, --config`: The YAML file containing the configuration for the tools to use and directories (default is `config.yaml`).
  - `-S, --case-sensitive`: Case-sensitive file search (default is case-insensitive, like Windows).

### Examples

- Extract all files and directories from all the NTFS partition in the image `image.E01` and save them in the `extracted_all` directory (or `extracted_all_0`, `extracted_all_1`, etc. if there are several partitions):

  ```sh
  ./main.py image.E01 -a -d extracted_all
  ```

- List all partitions and exit:

  ```sh
  ./main.py image.E01 -l
  ```

- Extract `NTUSER.DAT` for all users from the second partition:

  ```sh
  ./main.py image.E01 -p 2 -f "Users/*/NTUSER.DAT"
  ```

- Extract files and directories from the second and fourth partitions as specified in `files.yaml`:

  ```sh
  ./main.py image.E01 -p 2 4 -F files.yaml
  ```

- Ask for which partitions to use, and extract files as specified in `test1.yaml` and `test2.yaml`, using config from `config_test.yaml`:

  ```sh
  ./main.py image.E01 -P -F test1.yaml -F test2.yaml -c config_test.yaml
  ```

- List files and directories that match `*.sys` (in the root directory) and `Users/*/Desktop/*.lnk` from the NTFS partitions, as well as those listed in `files.yaml`:

  ```sh
  ./main.py image.E01 -f "*.sys" "Users/*/Desktop/*.lnk" -F files.yaml
  ```

- (On Windows) Extract the `.ssh` directory for all users (and root) in the second partition (using case-sensitive search as it is a Linux image), specifying where to find the TSK tools and that it is a RAW image with a GUID partition table, and save the output in the `extracted_linux` directory:

  ```powershell
  python3 main.py linux.img -T "..\tools\sleuthkit-4.12.1-win32\bin" -i raw -t gpt -p 2 -S -f "/home/*/.ssh" "/root/.ssh" -d extracted_linux
  ```

## YAML files

### Configuration file

Configuration is stored in a YAML file (default is `config.yaml`). It specifies a list of tools that can be used on extracted files, as well as the paths where the tool binaries are located.

Anywhere a path, command, or argument is specified, you can use variables in the form `$VAR_NAME`, or predefined functions in the form `${FUNC_NAME:arg1,arg2,...}`.
See the [Variables](#variables) section below for more information.

#### Structure

```yaml
tools: <list (required): list of tools>
  - name: <string (required): tool name>

    cmd: <string (required): command to execute>
    ### or ###
    cmd: <dict (required): command to execute, depending on the system (at least one is required)>
      windows: <string (optional): command to execute on Windows>
      linux: <string (optional): command to execute on Linux>
      macos: <string (optional): command to execute on MacOS (if not specified, the Linux command will be used)>

    args: <string (optional): command arguments that will always be added>

    args_extra: <dict (optional): extra arguments that can be added to the command (see File list infos)>
      arg1_name: <string (optional): extra argument 1 value>
      arg2_name: <string (optional): extra argument 2 value>
      ...

    allow_fail: <bool (optional): whether to continue if the tool fails (default is to False)>

    enabled: <bool (optional): whether the tool is enabled (default is True)>

    disabled: <bool (optional): whether the tool is disabled (default is False)>

  - ...

directories: <dict (optional): directories where the tools are located>
  tool1_name: <string (optional): path to the tool 1 binary directory>
  tool2_name: <string (optional): path to the tool 2 binary directory>
  ...

```

#### Included tools

- `regripper`: Extract information from Windows registry files.
  - Install the required binaries:
    - **Windows**: Download it from [https://github.com/keydet89/RegRipper3.0](https://github.com/keydet89/RegRipper3.0)
      - Don't forget to adjust the path in the config file, or put it in `../tools/RegRipper3.0`.
    - **Linux**: Install it with your package manager (eg. `sudo apt install regripper` on Debian/Ubuntu).
  - Optional arguments:
    - `plugin`: The plugin to use (eg. `userassist`, `recentdocs`, `usbstor`, etc.).
    - `profile`: The profile to use (eg. `system`, `software`, `ntuser`, etc.).
    - `all`: Automatically run hive-specific plugins
    - `all_tln`: Automatically run hive-specific TLN plugins (timeline)

- `srum_dump`: Extract information from the SRUM database.
  - Install the required binaries:
    - Download it from [https://github.com/MarkBaggett/srum-dump](https://github.com/MarkBaggett/srum-dump)
      - Don't forget to adjust the path in the config file, or put it in `../tools/srum-dump`.
  - Optional arguments:
    - `reg_hive`: If SOFTWARE registry hive is provided then the names of the network profiles will be resolved.
    - `xlsx_outfile`: Path to the XLS file that will be created.
    - `xlsx_template`: The Excel template that specifies what data to extract from the SRUM database.

- `evtx_dump`: Extract information from Windows event log files as XML or JSON.
  - Install the required binaries:
    - Download it from [https://github.com/omerbenamram/evtx](https://github.com/omerbenamram/evtx)
      - Don't forget to adjust the path in the config file, or put `evtx_dump.exe` directly in `../tools/`.
    - Alternatively, you can build it with `cargo install evtx` (see README on GitHub).
  - Optional arguments:
    - `format`: Sets the output format (default: `xml`). Possible values: `json`, `xml`, `jsonl`.
    - `output`: Writes output to the file specified instead of stdout, errors will still be printed to stderr.
    - `events`: When set, only the specified events (offset relative to file) will be output.

- `print`: Print a text to STDOUT.
  - Arguments:
    - `text`: The text to print.

- `print_newline`: Print a newline to STDOUT.

- `print_filename`: Print the name of the current file/directory to STDOUT.

- `print_filename_separated`: Print the name of the current file/directory to STDOUT, surrounded by separators:

  ```text
  --------------------
  File: path/to/file.ext
  --------------------
  ```

- `mkdir`: Create a directory, including all intermediate directories.
  - Arguments:
    - `dir`: The directory to create.

- `rm`: Delete a file.
  - Arguments:
    - `path`: Path to the file to delete.

- `rmdir`: Delete a directory and all its contents, recursively.
  - Arguments:
    - `path`: Path to the directory to delete.

#### Examples

See [`config.yaml`](config.yaml) for examples.

### File list

The file list is a YAML file that contains the files and directories to extract, as well as the tools to run on them and their options.

Paths can be absolute or relative to the root of the partition, with or without `C:`, and separated by `/` or `\`.
For instance, the following paths are all equivalent:

- `Users/Test/Documents/file.pdf`
- `Users\Test\Documents\file.pdf`
- `/Users/Test/Documents/file.pdf`
- `\Users\Test\Documents\file.pdf`
- `C:/Users/Test/Documents/file.pdf`
- `C:\Users\Test\Documents\file.pdf`

Wildcards are also allowed (eg. `Users/*/Documents/*.pdf`).

In tools config, anywhere a path, command, or argument is specified, you can use variables in the form `$VAR_NAME`, or predefined functions in the form `${FUNC_NAME:arg1,arg2,...}`.
See the [Variables](#variables) section below for more information.

#### Structure

```yaml
files: <list (required): list of files and directories to extract>
  - <string (required): file or directory path; no tools will be run on it>
  ### or ###
  - path: <string (required): file or directory path>

    tool: <dict (optional): settings for the tool to run on the extracted file/dir>

      # At least one of name or cmd is required
      name: <string (optional): tool name, as defined in the config file>
      cmd: <string (optional): command to execute>

      extra: <dict (optional): extra arguments that can be added to the command (see above in the Configuration section)>
        arg1_name: <string (optional): extra argument 1 value>
        arg2_name: <string (optional): extra argument 2 value>
        ...

      filter: <string (optional): only run the tool if the file matches the filter (eg. `*.pdf`, `*.evtx`, etc.)>

      output: <string (optional): redirect STDOUT to the given file (if not specified, the output will be printed to the console)>
      ### or ###
      output: <dict (optional): output file settings>
        path: <string (required): path to the output file>
        append: <bool (optional): whether to append to the output file (default is False, ie. overwrite)>
        stderr: <bool (optional): whether to also redirect stderr to the output file (default is False)>

      requires: <list (optional): list of files or directories that must be extracted before this tool can run>
        - <string (optional): file or directory path>
        - ...

      allow_fail: <bool (optional): whether to continue if the tool fails, superseding tool setting from the config if set>

      run_once: <bool (optional): whether to run the tool only once, even if the file is extracted multiple times (default is False)>

    tools: <list (optional): list of tools to run on the extracted file/dir>
      - <Tool settings (see above)>
      - ...

    overwrite: <bool (optional): if False, skip extraction if the file already exists (default is True)>

  - ...
```

#### Examples

See [`files.yaml`](files.yaml) for examples.

### Variables
