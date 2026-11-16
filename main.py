import argparse
import sys
from pathlib import Path

from realty_ledger import DeveloperAccountingEngine, StatementExporter


def run():
    parser = argparse.ArgumentParser(description="PS-094 Real Estate Developer Billing Engine")
    parser.add_argument("--data-dir", default="sample_data", help="Folder with input CSVs and commands.txt")
    parser.add_argument("--out-dir", default="output", help="Destination folder for output CSV reports")
    parser.add_argument("--quiet", action="store_true", help="Skip printing statements to stdout")
    args = parser.parse_args()

    input_dir = Path(args.data_dir)
    engine = DeveloperAccountingEngine()
    engine.load_csv_inputs(str(input_dir))

    with open(input_dir / "commands.txt", "r", encoding="utf-8") as cmd_fh:
        for idx, raw_line in enumerate(cmd_fh, start=1):
            try:
                text_out = engine.run_command(raw_line)
                if text_out and not args.quiet:
                    print(text_out)
                    print()
            except Exception as err:
                print(f"Error on command line {idx}: {raw_line.strip()} -> {err}", file=sys.stderr)
                raise

    StatementExporter.write_all_csvs(engine, args.out_dir)
    if not args.quiet:
        print(f"Saved output CSV files to: {Path(args.out_dir).resolve()}")


if __name__ == "__main__":
    run()
