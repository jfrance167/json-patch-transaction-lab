"""Create an exclusive synthetic demo report; never collect external documents."""
from pathlib import Path
import sys
from patch_lab.__main__ import main as cli_main

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    """Reuse checked primary CLI; complete rollback demo intentionally exits 4."""
    args = sys.argv[1:] if argv is None else argv
    return cli_main([str(ROOT / "samples/demo.json"), *args])


if __name__ == "__main__":
    raise SystemExit(main())
