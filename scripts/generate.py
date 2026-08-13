"""Write the distributable workbook to ``dist/greggs_model.xlsx``.

The repository's one entry point for producing the artefact. Run it from the
project root::

    python3 scripts/generate.py [scenario]

`scenario` defaults to ``Base`` and only sets the starting position of the
switch in ``Assumptions!C3`` — all three scenarios' driver paths are written
to the sheet regardless, so the switch in the delivered file is a real toggle
and the choice here is presentational.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The test suite gets `src` on the path from pyproject; a plain `python3
# scripts/generate.py` does not, so put it there rather than require the
# caller to remember PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bluebook.inputs.greggs import GREGGS_HISTORICALS  # noqa: E402
from bluebook.workbook.build import build_workbook  # noqa: E402

DEFAULT_SCENARIO = "Base"
OUTPUT = Path(__file__).resolve().parent.parent / "dist" / "greggs_model.xlsx"


def main(argv: list[str]) -> int:
    scenario = argv[1] if len(argv) > 1 else DEFAULT_SCENARIO
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    path = build_workbook(GREGGS_HISTORICALS, scenario, OUTPUT)
    print(f"wrote {path} (scenario switch starts on {scenario})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
