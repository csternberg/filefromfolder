#!/usr/bin/env python3
"""Rename files in a folder to <name>_001.<ext>, <name>_002.<ext>, ...

<name> is either a fixed string (-S) or the name of the parent folder (-F).
Files that share a base name but differ in extension (file1.gif, file1.jpg)
are treated as one group and get the same number.

Run with -H for the full option list.
"""
import argparse
import logging
import os
import re
import sys
from collections import defaultdict

BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SCRIPT_PATH = os.path.normcase(os.path.abspath(__file__))
log = logging.getLogger("filefromfolder")


class Stats:
    def __init__(self):
        self.renamed = 0
        self.skipped = 0
        self.errors = 0


def natural_key(text):
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]


def scan(directory, quiet=False):
    """Return (file names, sub-folder names, every name present) for a folder.

    Hidden entries (leading dot) and symlinks are never touched. Unreadable
    folders or entries are logged and skipped.
    """
    files, dirs, everything = [], [], []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                everything.append(entry.name)
                if entry.name.startswith(".") or entry.is_symlink():
                    continue
                try:
                    if entry.is_file():
                        files.append(entry.name)
                    elif entry.is_dir():
                        dirs.append(entry.name)
                except OSError as exc:
                    log.warning("Cannot inspect %s: %s", entry.path, exc)
    except OSError as exc:
        if not quiet:
            log.error("Cannot read folder %s: %s", directory, exc)
    return files, sorted(dirs, key=natural_key), everything


def rename_group(pairs):
    """Rename every (src, dst) in a group; undo the group if one fails."""
    done = []
    try:
        for src, dst in pairs:
            if os.path.lexists(dst):  # os.rename would overwrite on POSIX
                raise FileExistsError(f"target already exists: {dst}")
            os.rename(src, dst)
            done.append((src, dst))
    except OSError as exc:
        log.error("Cannot rename %s: %s", pairs[len(done)][0], exc)
        for src, dst in reversed(done):
            try:
                os.rename(dst, src)
            except OSError as exc2:
                log.error("Rollback failed, %s is now %s: %s", src, dst, exc2)
        return False
    return True


def already_named_re(base):
    """Matches the stem of a file already named base_NNN or base_NNN_suffix."""
    return re.compile(rf"^{re.escape(base)}_(\d+)(?:_.*)?$", re.IGNORECASE if os.name == "nt" else 0)


def group_stems(stems):
    """Map each stem to its group root: the shortest other stem that is a
    prefix of it followed by '_' (file1_high -> file1), else itself."""
    known = {os.path.normcase(st) for st in stems}
    roots = {}
    for st in stems:
        roots[st] = st
        for i, ch in enumerate(st):
            if ch == "_" and i > 0 and os.path.normcase(st[:i]) in known:
                roots[st] = st[:i]
                break
    return roots


def process_dir(directory, base, args, root, stats, skip_paths, used):
    """Rename the files directly inside `directory`. Returns sub-folder names.

    `used` is the set of numbers already taken in the numbering scope; it is
    updated as numbers are assigned.
    """
    files, dirs, everything = scan(directory)

    already = already_named_re(base)
    entries = []  # (stem, ext)
    for name in files:
        if os.path.normcase(os.path.join(directory, name)) in skip_paths:
            continue
        stem, ext = os.path.splitext(name)
        m = already.match(stem)
        if m:
            used.add(int(m.group(1)))
            stats.skipped += 1
            log.debug("Skip (already named): %s", os.path.join(directory, name))
            continue
        entries.append((stem, ext))

    roots = group_stems([st for st, _ in entries])
    groups = {}  # normcased root -> (root, [(suffix, ext)])
    for stem, ext in entries:
        root_stem = roots[stem]
        groups.setdefault(os.path.normcase(root_stem), (root_stem, []))[1].append(
            (stem[len(root_stem):], ext))

    occupied = {os.path.normcase(n) for n in everything}
    counter = 1
    for group_root, members in sorted(groups.values(), key=lambda g: natural_key(g[0])):
        members.sort(key=lambda m: (m[0].casefold(), m[1].casefold()))
        while True:
            targets = [f"{base}_{counter:03d}{suf}{ext}" for suf, ext in members]
            if counter not in used and not any(os.path.normcase(t) in occupied for t in targets):
                break
            counter += 1
        used.add(counter)
        occupied.update(os.path.normcase(t) for t in targets)
        pairs = [
            (os.path.join(directory, group_root + suf + ext), os.path.join(directory, t))
            for (suf, ext), t in zip(members, targets)
        ]
        counter += 1

        if args.dry_run:
            for src, dst in pairs:
                log.info("[DRY-RUN] %s -> %s", os.path.relpath(src, root), os.path.basename(dst))
            stats.renamed += len(pairs)
        elif rename_group(pairs):
            for src, dst in pairs:
                log.info("%s -> %s", os.path.relpath(src, root), os.path.basename(dst))
            stats.renamed += len(pairs)
        else:
            stats.errors += len(pairs)
    return dirs


def collect_used(root, base, skip_paths):
    """Numbers already used by files named base_NNN[_x] anywhere under root."""
    used, pending, already = set(), [root], already_named_re(base)
    while pending:
        directory = pending.pop()
        files, dirs, _ = scan(directory, quiet=True)
        for name in files:
            m = already.match(os.path.splitext(name)[0])
            if m and os.path.normcase(os.path.join(directory, name)) not in skip_paths:
                used.add(int(m.group(1)))
        pending.extend(os.path.join(directory, d) for d in dirs)
    return used


def build_parser():
    p = argparse.ArgumentParser(
        prog="filefromfolder.py",
        add_help=False,
        allow_abbrev=True,
        description="Rename files to <name>_001.<ext>, <name>_002.<ext>, ... "
        "Files with the same base name but different extensions share a number, "
        "as do files named <base>_<anything> (file1.jpg + file1_high.mp4 -> "
        "<name>_001.jpg + <name>_001_high.mp4).",
        epilog="Hidden files (leading dot), symlinks and sub-folders themselves "
        "are never renamed. Files already named <name>_<digits>[_x] are left alone, "
        "so re-running is safe.",
    )
    p.add_argument("folder", nargs="?", default=".",
                   help="folder to process (default: current folder)")
    name = p.add_mutually_exclusive_group(required=True)
    name.add_argument("-S", "-s", "--string", metavar="STRING",
                      help="name files STRING_001.ext, STRING_002.ext, ...")
    name.add_argument("-F", "-f", "--folder-name", dest="use_folder", action="store_true",
                      help="name files after their parent folder")
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("-C", "-c", "--current", action="store_true",
                       help="only files in the current folder (default)")
    scope.add_argument("-R", "-r", "--recursive", action="store_true",
                       help="current folder and all sub-folders")
    p.add_argument("-P", "-p", "--path", action="store_true",
                   help="with -F -R: name sub-folder files parent-sub[-subsub...]; "
                   "ignored with -S or -C")
    p.add_argument("-E", "-e", "--restart", action="store_true",
                   help="with -S -R: restart numbering at 001 in every sub-folder "
                   "(default: numbers are unique across all folders)")
    p.add_argument("-D", "-d", "--dry-run", action="store_true",
                   help="show what would be renamed without renaming")
    p.add_argument("-L", "-l", "--log", metavar="FILE",
                   help="also write a timestamped log to FILE (appended)")
    p.add_argument("-H", "-h", "--help", action="help", help="show this help and exit")
    return p


def setup_logging(logfile):
    log.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)
    if logfile:
        try:
            fh = logging.FileHandler(logfile, mode="a", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(fh)
        except OSError as exc:
            log.error("Cannot open log file %s: %s (continuing without it)", logfile, exc)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.log)

    if args.string is not None:
        if not args.string or BAD_CHARS.search(args.string) or args.string.endswith((" ", ".")):
            parser.error("-S string is empty or contains characters not allowed in file names")
    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        parser.error(f"not a folder: {root}")

    use_path = args.path
    if args.path and (args.string is not None or not args.recursive):
        log.warning("Note: -P ignored (only applies with -F -R).")
        use_path = False

    if args.restart and not (args.string is not None and args.recursive):
        log.warning("Note: -E ignored (only applies with -S -R).")
    global_numbers = args.string is not None and args.recursive and not args.restart

    skip_paths = {SCRIPT_PATH}
    if args.log:
        skip_paths.add(os.path.normcase(os.path.abspath(args.log)))

    root_name = os.path.basename(root) or "root"
    stats = Stats()
    used = collect_used(root, args.string, skip_paths) if global_numbers else None
    log.info("%sProcessing %s%s", "[DRY-RUN] " if args.dry_run else "", root,
             " (recursive)" if args.recursive else "")

    stack = [(root, [])]  # (folder, path parts below root)
    while stack:
        directory, parts = stack.pop()
        if args.string is not None:
            base = args.string
        elif use_path:
            base = "-".join([root_name] + parts)
        else:
            base = os.path.basename(directory) or "root"
        subdirs = process_dir(directory, base, args, root, stats, skip_paths,
                              used if global_numbers else set())
        if args.recursive:
            # reversed so folders are visited in sorted order
            stack.extend((os.path.join(directory, d), parts + [d]) for d in reversed(subdirs))

    log.info("Done: %d renamed, %d already named, %d errors%s", stats.renamed,
             stats.skipped, stats.errors, " (dry run, nothing changed)" if args.dry_run else "")
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
