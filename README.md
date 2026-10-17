# filefromfolder

A single-file Python 3 utility (standard library only) that renames files to
`<name>_001.<ext>`, `<name>_002.<ext>`, ... where `<name>` is a string you give
or the name of the file's parent folder.

Files with the same base name but different extensions are grouped and get the
same number: with `-S newname`, `file1.gif` and `file1.jpg` become
`newname_001.gif` and `newname_001.jpg`.

## Usage

```
python filefromfolder.py (-S STRING | -F) [-C | -R] [-P] [-E] [-D] [-L FILE] [-H] [folder]
```

| Option | Meaning |
|---|---|
| `-S STRING` | Name files `STRING_001.ext`, `STRING_002.ext`, ... |
| `-F` | Name files after their parent folder. |
| `-C` | Only files directly in the folder (default). |
| `-R` | The folder and all sub-folders. |
| `-P` | With `-F -R`: sub-folder files are named `parent-sub[-subsub...]`. Ignored with `-S` or `-C`. |
| `-E` | With `-S -R`: restart numbering at 001 in every sub-folder. Default: numbers are unique across all folders. |
| `-D` | Dry run: show what would happen, change nothing. |
| `-L FILE` | Also append a timestamped log to `FILE`. |
| `-H` | Help. |
| `folder` | Optional; defaults to the current folder. |

Every short option works in upper or lower case (`-s`, `-r`, `-d`...) and has a
long form (`--string`, `--folder-name`, `--current`, `--recursive`, `--path`, `--restart`,
`--dry-run`, `--log`, `--help`); unambiguous abbreviations such as `--dry` work too.

Exactly one of `-S` / `-F` is required; `-C` and `-R` are mutually exclusive.

## Examples

```
python filefromfolder.py -S holiday -D            # preview
python filefromfolder.py -S holiday               # holiday_001.jpg, holiday_002.jpg ...
python filefromfolder.py -S holiday -R            # numbers continue across sub-folders
python filefromfolder.py -S holiday -R -E         # restart at 001 in each sub-folder
python filefromfolder.py -F -R                    # each file named after its own folder
python filefromfolder.py -F -R -P -L rename.log   # root-sub_001.jpg, root-sub-deep_001.jpg ...
```

## Behaviour

- **Numbering** starts at 001 (3 digits, grows if needed) and follows a natural
  sort of the original base names (`img2` before `img10`). With `-S -R` the
  numbers are unique across all folders (the sequence continues into each
  sub-folder); add `-E` to restart at 001 in every folder. With `-F` numbering
  is always per folder.
- **Grouping:** `file1.gif`, `file1.jpg` share a number, and so do files named
  `file1_<anything>.<ext>` when a `file1.*` exists: `file1.jpg` and
  `file1_high.mp4` become `holiday_001.jpg` and `holiday_001_high.mp4` (with
  `-S holiday`). If several bases match, the shortest wins. A `name_xxx` file
  with no matching `name.*` is a group of its own.
- **Collisions:** if a number is already used in scope, or any target name in a
  group already exists, the number is increased until the whole group is free.
  Nothing is ever overwritten.
- **Re-runnable:** files already named `<name>_<digits>[_x].<ext>` are left
  alone (their numbers count as used).
- **`-P`** builds the name from the start folder's name plus each sub-folder
  down to the file (`photos-2024-june_001.jpg`). Files directly in the start
  folder are named after it.
- **Never touched:** hidden files/folders (leading `.`), symlinks, folders
  themselves, the log file and the script itself.
- **Errors** (locked, unreadable, permission denied, name too long...) are
  logged and skipped; a partly renamed group is rolled back. Exit code is
  `0` on success, `1` if any file failed, `2` on bad arguments.
