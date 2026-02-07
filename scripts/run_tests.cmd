@echo off
set PYTHON=python
if not "%1"=="" set PYTHON=%1

%PYTHON% -m pytest -q
if errorlevel 1 (
  echo Tests failed.
  exit /b 1
)

echo All tests passed.
