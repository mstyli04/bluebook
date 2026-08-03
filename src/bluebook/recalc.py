"""Recalculate openpyxl-generated workbooks through headless LibreOffice.

openpyxl writes formulas without cached results, so LibreOffice must evaluate
them on load. Converting the file back to xlsx persists those results, which
openpyxl can then read with data_only=True.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl

SOFFICE = "soffice"
TIMEOUT_SECONDS = 180


class RecalcError(RuntimeError):
    """LibreOffice failed to recalculate the workbook."""


def recalc(path: Path) -> Path:
    """Recalculate `path` and return the path of the recalculated copy.

    The copy lives in a temporary directory that persists for the process
    lifetime; callers that need it long-term should copy it out.
    """
    path = Path(path).resolve()
    outdir = Path(tempfile.mkdtemp(prefix="bluebook-recalc-"))
    # An isolated user profile lets this run alongside a desktop LibreOffice
    # and keeps concurrent test runs from clashing over one profile lock.
    profile = outdir / "profile"
    result = subprocess.run(
        [
            SOFFICE,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--norestore",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(outdir),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    recalculated = outdir / path.name
    if not recalculated.exists():
        raise RecalcError(
            f"LibreOffice produced no output for {path}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return recalculated


def recalc_values(path: Path) -> dict[str, dict[str, object]]:
    """Recalculate `path` and return {sheet: {cell_address: computed value}}."""
    recalculated = recalc(path)
    wb = openpyxl.load_workbook(recalculated, data_only=True)
    out: dict[str, dict[str, object]] = {}
    for ws in wb.worksheets:
        cells: dict[str, object] = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells[cell.coordinate] = cell.value
        out[ws.title] = cells
    wb.close()
    shutil.rmtree(recalculated.parent / "profile", ignore_errors=True)
    return out
