"""Locate portable application resources without relying on a developer's drive."""
from pathlib import Path
import sys

APP_VERSION = '0.2.0-dev'


def application_directory():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
