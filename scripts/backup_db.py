import argparse
from contextlib import closing
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description="Zrób spójną kopię bazy Prawdowidu.")
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not args.database.is_file() or args.output.exists():
        parser.error("Potrzebna istniejąca baza i nowa ścieżka kopii.")
    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        with args.output.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(args.output)) as destination:
                source.backup(destination)
        except Exception:
            args.output.unlink()
            raise


if __name__ == "__main__":
    main()
