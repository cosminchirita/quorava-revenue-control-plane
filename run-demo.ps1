$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e .
& ".\.venv\Scripts\python.exe" scripts\bootstrap_demo.py
& ".\.venv\Scripts\python.exe" -m quorava serve --host 127.0.0.1 --port 8787
