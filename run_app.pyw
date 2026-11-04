"""Double-click entry point; shortcuts use pythonw so no console is created."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from faceguard.launcher import launch

if __name__ == '__main__':
    raise SystemExit(launch())
