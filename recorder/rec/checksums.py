"""SHA-256 checksums of a session folder, so a damaged or changed file can be spotted later.

`checksums.sha256` holds one line per file, "<hex>  <relative path>", the format `shasum -a 256 -c` reads.
Hidden files (.DS_Store, macOS's ._ files on the exFAT SSD) are neither hashed nor reported. A checksum only
shows that a file is the same as when it was hashed, not that it was right then, and it can't repair anything.
"""
import hashlib
from pathlib import Path

NAME = "checksums.sha256"
_SKIP = {NAME, NAME + ".tmp"}


def _files(folder):
    """Relative posix paths of every file to hash, sorted."""
    out = []
    for p in Path(folder).rglob("*"):
        rel = p.relative_to(folder)
        if any(part.startswith(".") for part in rel.parts) or rel.as_posix() in _SKIP or not p.is_file():
            continue
        out.append(rel.as_posix())
    return sorted(out)


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def write(folder, overwrite=False):
    """Hash every file in the folder into checksums.sha256. Returns the number of files, or None if a
    checksum file already exists and overwrite is False (an existing record is never replaced by default)."""
    folder = Path(folder)
    target = folder / NAME
    if target.exists() and not overwrite:
        return None
    names = _files(folder)
    lines = [f"{sha256(folder / n)}  {n}\n" for n in names]
    tmp = folder / (NAME + ".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(target)  # never leave a half-written checksum file
    return len(names)


def read(folder):
    """{relative path: hex} from checksums.sha256, or None if there is none."""
    target = Path(folder) / NAME
    if not target.exists():
        return None
    out = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, _, name = line.partition("  ")
            out[name.lstrip("*")] = digest.strip().lower()
    return out


def verify(folder):
    """{"status": ok | changed | no checksum, "files", "changed", "missing", "extra"} for one session folder.
    `extra` (files added since) is reported but does not make the status "changed"."""
    folder = Path(folder)
    known = read(folder)
    if known is None:
        return {"status": "no checksum", "files": 0, "changed": [], "missing": [], "extra": []}
    present = set(_files(folder))
    missing = sorted(n for n in known if n not in present)
    changed = sorted(n for n in known if n in present and sha256(folder / n) != known[n])
    extra = sorted(present - set(known))
    status = "changed" if changed or missing else "ok"
    return {"status": status, "files": len(known), "changed": changed, "missing": missing, "extra": extra}
