"""Locate external models in both source and installed applications."""
from pathlib import Path
import sys


def application_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
