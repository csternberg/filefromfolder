# CLAUDE.md

## Project
`filefromfolder.py` is a deliberately **single-file**, **stdlib-only** Python 3
CLI that batch-renames files to `<name>_NNN.<ext>`. See `README.md` for the
user-facing spec; keep it in sync when behaviour or options change.

## Rules to preserve
- Keep everything in `filefromfolder.py`; no third-party dependencies.
- Flags `-S -F -C -R -P -E -D -L -H` each accept upper or lower case and have a `--long` form; `-H`/`-h` is help.
- Files sharing a base name (differing extension), or named `base_<anything>` where `base.*` exists (shortest such base wins), form a group and share one number; the suffix is kept.
- `-S -R` numbers are unique across folders by default (pre-scan of used numbers); `-E` restarts per folder.
- Never overwrite: a group's number is bumped until all its targets are free.
- Failures (locked/unreadable/permission) are logged and skipped, never fatal;
  a partly renamed group is rolled back. Exit codes: 0 ok, 1 file errors, 2 usage.
- Skip hidden entries, symlinks, the script itself and the log file.
- `-P` only applies with `-F -R`; otherwise warn and ignore.
- Dry run (`-D`) must use the same planning code path as a real run.

## Testing
No test suite. Verify manually in a temp folder with a mix of grouped
extensions, a pre-existing target name, sub-folders, and `-D` before/after:

```
python filefromfolder.py -S newname -D
python filefromfolder.py -F -R -P -D
python filefromfolder.py -S x -R -D      # then again with -E
```

Include `file1.jpg` + `file1_high.mp4` to check suffix grouping.
