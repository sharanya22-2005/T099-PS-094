import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from billing_engine import BillingEngine


def run_file(filepath: str):
    engine = BillingEngine()
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            try:
                output = engine.execute_command_line(line)
                if output:
                    print(output)
                    print()
            except Exception as exc:
                print(f"[ERROR on line {line_no}] {line.strip()} -> {exc}", file=sys.stderr)
                raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <command_file_path>")
        sys.exit(1)
    run_file(sys.argv[1])
