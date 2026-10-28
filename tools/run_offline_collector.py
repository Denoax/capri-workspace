"""Run the declared suite through the unchanged isolated collector, without models."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'controller'))
from loop.collector import check_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', choices=('runtime', 'runtime-unit', 'benchmark'), default='runtime')
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        parser.error('Evidence output must be outside the source checkout')
    argv = (['python3', '-m', 'unittest', '-v', 'tests.collector_runtime'] if args.suite == 'runtime-unit'
            else ['python3', '-m', 'unittest', 'discover', '-s', 'controller/tests' if args.suite == 'runtime' else 'tests', '-v'])
    minimum = {'runtime':343, 'runtime-unit':339, 'benchmark':12}[args.suite]
    result = check_command(ROOT, argv, args.output)
    run = result.get('test_run') or {}
    passed = (result['exit'] == 0 and not result['timeout'] and not result['skip_detected'] and
              result['source_unchanged'] and run.get('complete') and
              run.get('outcome') == 'PASSED' and run.get('count', 0) >= minimum)
    print(json.dumps(dict(status='PASS' if passed else 'FAIL', suite=args.suite,
                         tests=run.get('count'), exit=result['exit'],
                         source_unchanged=result['source_unchanged'], evidence=str(args.output),
                         coverage='Host-only cases are explicit in tests/collector_runtime.py; this is not a full343 collector result' if args.suite == 'runtime-unit' else 'Complete named suite')))
    if not passed:
        # Collector output is already redacted. Retain the complete files as
        # artifacts and expose a bounded diagnostic tail in the job log.
        for name in ('stdout.txt', 'stderr.txt'):
            path = args.output/name
            if path.is_file():print(name+' (last 16000 characters):\n'+path.read_text()[-16000:])
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
