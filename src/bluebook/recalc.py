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

    The copy lives in a fresh temporary directory that this function does
    NOT clean up: the caller owns that directory and decides when it's done
    with it (callers that need the file long-term should copy it out).
    `recalc_values()` is the one exception — it extracts every value it
    needs from the copy before returning, so it deletes the directory
    itself; see its docstring.
    """
    path = Path(path).resolve()
    outdir = Path(tempfile.mkdtemp(prefix="bluebook-recalc-"))
    # An isolated user profile lets this run alongside a desktop LibreOffice
    # and keeps concurrent test runs from clashing over one profile lock.
    profile = outdir / "profile"
    try:
        try:
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
        except subprocess.TimeoutExpired as exc:
            raise RecalcError(
                f"LibreOffice timed out after {TIMEOUT_SECONDS}s recalculating {path}.\n"
                f"stdout: {exc.stdout}\nstderr: {exc.stderr}"
            ) from exc
        except FileNotFoundError as exc:
            raise RecalcError(
                f"Could not find the '{SOFFICE}' executable to recalculate {path}. "
                f"Is LibreOffice installed and on PATH? ({exc})"
            ) from exc

        recalculated = outdir / path.name
        if result.returncode != 0 or not recalculated.exists():
            raise RecalcError(
                f"LibreOffice failed to recalculate {path} "
                f"(exit code {result.returncode}).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
    except RecalcError:
        # There is no output path to hand ownership of outdir to, so this
        # function must clean up after itself rather than leak it.
        shutil.rmtree(outdir, ignore_errors=True)
        raise
    return recalculated


def recalc_values(path: Path) -> dict[str, dict[str, float | str | bool | None]]:
    """Recalculate `path` and return {sheet: {cell_address: computed value}}.

    Unlike `recalc()`, this function owns the temporary directory `recalc()`
    creates end to end: it has already read every value it needs out of the
    recalculated copy before returning, so it removes that directory itself
    instead of leaking it back to the caller.
    """
    recalculated = recalc(path)
    try:
        wb = openpyxl.load_workbook(recalculated, data_only=True)
        out: dict[str, dict[str, float | str | bool | None]] = {}
        for ws in wb.worksheets:
            cells: dict[str, float | str | bool | None] = {}
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        cells[cell.coordinate] = cell.value
            out[ws.title] = cells
        wb.close()
    finally:
        shutil.rmtree(recalculated.parent, ignore_errors=True)
    return out
