from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        raise SystemExit("Python compilation failed")
    run("scripts/bootstrap_demo.py")
    run("-m", "unittest", "discover", "-s", "tests", "-v")
    run("scripts/verify_demo.py")
    print("All Quorava checks passed.")


if __name__ == "__main__":
    main()

