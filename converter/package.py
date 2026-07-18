"""Write the file map to a workspace source folder and a .scwsp archive."""

from __future__ import annotations

import os
import zipfile

def write_workspace(files: dict[str, object], output_dir: str, course_safe: str,
                    make_scwsp: bool = True) -> tuple[str, str | None]:
    """files: {relpath-from-workspace-root -> str|bytes}.

    Writes to <output_dir>/<course_safe>/… and (optionally) zips a
    <output_dir>/<course_safe>.scwsp with .wspmeta at the archive root.
    Returns (workspace_dir, scwsp_path|None).
    """
    root = os.path.join(output_dir, course_safe)
    for rel, content in files.items():
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if isinstance(content, bytes):
            with open(dest, "wb") as f:
                f.write(content)
        else:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)

    scwsp = None
    if make_scwsp:
        scwsp = os.path.join(output_dir, course_safe + ".scwsp")
        with zipfile.ZipFile(scwsp, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel, content in files.items():
                if isinstance(content, str):
                    zf.writestr(rel, content.encode("utf-8"))
                else:
                    zf.writestr(rel, content)
    return root, scwsp
