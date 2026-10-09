"""Output path resolution and conflict policies (spec §6, §7)."""
import os
from pathlib import Path

from app.engine.errors import PermissionDenied


def target_filename(src_name: str, target_fmt: str) -> str:
    """Basename + target extension; keeps Chinese/spaces as-is."""
    return Path(src_name).stem + "." + target_fmt


def resolve_output_path(
    target_filename: str,
    rel_subdir: str,
    out_dir: str,
    conflict: str,
    exists=os.path.exists,
) -> str | None:
    """Final absolute output path. None = skip (caller marks SKIPPED).

    Renaming happens here, at execution time (scheduler is serial, no races).
    """
    base = Path(out_dir)
    if rel_subdir:
        base = base / rel_subdir
    candidate = base / target_filename

    if conflict == "overwrite":
        return str(candidate)
    if conflict == "skip":
        return None if exists(str(candidate)) else str(candidate)
    if conflict == "rename":
        if not exists(str(candidate)):
            return str(candidate)
        stem = Path(target_filename).stem
        ext = Path(target_filename).suffix
        i = 1
        while True:
            cand = base / f"{stem}_{i}{ext}"
            if not exists(str(cand)):
                return str(cand)
            i += 1
    raise ValueError(f"unknown conflict policy: {conflict}")


def ensure_output_dir(final_path: str) -> None:
    try:
        os.makedirs(str(Path(final_path).parent), exist_ok=True)
    except OSError as e:
        raise PermissionDenied(f"cannot create output directory for {final_path}: {e}") from e
