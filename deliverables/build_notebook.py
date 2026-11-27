"""Build ``walkthrough.ipynb`` from ``walkthrough.py``.

The script is the only thing to edit. Cells are split on its ``# %%`` lines;
``# %% [markdown]`` cells have their leading ``# `` removed. Run from the
project folder::

    python deliverables/build_notebook.py             # build and run (network)
    python deliverables/build_notebook.py --no-run    # build without outputs
    python deliverables/build_notebook.py --check     # is it up to date?
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "walkthrough.py"
NOTEBOOK = HERE / "walkthrough.ipynb"


def split_cells(source: str) -> list[tuple[str, str]]:
    """``(kind, text)`` for every cell of a ``# %%`` script, in order."""
    cells: list[tuple[str, list[str]]] = []
    for line in source.splitlines():
        if line.startswith("# %%"):
            kind = "markdown" if "[markdown]" in line else "code"
            cells.append((kind, []))
        elif cells:
            cells[-1][1].append(line)
        elif line.strip():
            raise ValueError("The script must start with a '# %%' line.")

    result = []
    for kind, lines in cells:
        if kind == "markdown":
            bad = [x for x in lines if x.strip() and not x.startswith("#")]
            if bad:
                raise ValueError(f"Code inside a markdown cell: {bad[0]!r}")
            lines = [x.removeprefix("#").removeprefix(" ") for x in lines]
        text = "\n".join(lines).strip("\n")
        if text:
            result.append((kind, text))
    return result


def build() -> nbformat.NotebookNode:
    makers = {"code": new_code_cell, "markdown": new_markdown_cell}
    cells = []
    for number, (kind, text) in enumerate(
        split_cells(SCRIPT.read_text(encoding="utf-8"))
    ):
        cell = makers[kind](text)
        # A fixed id, so rebuilding does not rewrite every cell in the diff.
        cell["id"] = f"cell-{number:02d}"
        cells.append(cell)
    metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python"},
    }
    return new_notebook(cells=cells, metadata=metadata)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--no-run", action="store_true", help="skip execution")
    group.add_argument("--check", action="store_true", help="compare only")
    args = parser.parse_args(argv)

    notebook = build()

    if args.check:
        if not NOTEBOOK.is_file():
            print(f"{NOTEBOOK.name} is missing.", file=sys.stderr)
            return 1
        saved = nbformat.read(NOTEBOOK, as_version=4)
        wanted = [(c.cell_type, c.source) for c in notebook.cells]
        found = [(c.cell_type, c.source) for c in saved.cells]
        if wanted != found:
            print(f"{NOTEBOOK.name} differs from {SCRIPT.name}.", file=sys.stderr)
            return 1
        print(f"{NOTEBOOK.name} matches {SCRIPT.name} ({len(found)} cells).")
        return 0

    if not args.no_run:
        from nbclient import NotebookClient

        # Raises on the first failing cell, leaving the old notebook in place.
        NotebookClient(
            notebook,
            timeout=300,
            kernel_name="python3",
            resources={"metadata": {"path": str(HERE)}},
            record_timing=False,
        ).execute()

    nbformat.validate(notebook)
    nbformat.write(notebook, NOTEBOOK)
    ran = "not run" if args.no_run else "run top to bottom"
    print(f"Wrote {NOTEBOOK.name} ({len(notebook.cells)} cells, {ran}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
