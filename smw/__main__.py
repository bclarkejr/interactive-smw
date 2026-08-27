import argparse
from datetime import date
from pathlib import Path

from smw.render.build import run_build

parser = argparse.ArgumentParser(description="Summer Movie Wager site builder")
parser.add_argument("--date", type=date.fromisoformat, default=date.today(),
                    help="run date (default: today); the only wall-clock input")
parser.add_argument("--data", type=Path, default=Path("data"))
parser.add_argument("--out", type=Path, default=Path("out"))
parser.add_argument("--local", action="store_true",
                    help="write the site but append to NO history file (dev runs)")
args = parser.parse_args()
run_build(args.data, args.out, args.date, local=args.local)
