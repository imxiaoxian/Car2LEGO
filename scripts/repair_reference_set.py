"""Resume a real reference generation from an inspected content review."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from car2lego3d.common import write_json
from car2lego3d.gpt_reference import generate
from car2lego3d.reference_review import repair_corrections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--prompt', required=True)
    args = parser.parse_args()
    correction_path = args.directory / 'reference-corrections.json'
    previous = json.loads(correction_path.read_text(encoding='utf-8')) if correction_path.is_file() else {}
    report = json.loads(args.review.read_text(encoding='utf-8'))
    write_json(correction_path, repair_corrections(report, previous))
    print(generate(args.prompt, args.directory, args.spec), flush=True)


if __name__ == '__main__':
    main()
