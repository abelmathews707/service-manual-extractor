"""Capture B1 sidecars from an immutable A10 generation without re-extracting.

Original package hashes are rechecked. Source packages are never modified.
Existing output files must agree exactly, making an interrupted run resumable.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from sme.evidence import capture_evidence


def read(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def write_once(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError(f'existing acceptance output differs: {path}')
        return
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accepted_generation', type=Path)
    parser.add_argument('vocabulary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    vocabulary = read(args.vocabulary)
    output = args.output / 'evidence'
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    for item in read(args.accepted_generation / 'library.json')['packages']:
        print(json.dumps({'stage': 'capture', 'source_id': item['source_id']}), flush=True)
        result = capture_evidence(str(args.accepted_generation / item['root']), vocabulary)
        write_once(output / (item['source_id'] + '.json'), result)
        print(json.dumps({'stage': 'captured', 'source_id': result['source_id'],
                          'revision': result['revision'], 'units': len(result['units']),
                          'elapsed_seconds': round(perf_counter() - started, 2)}), flush=True)


if __name__ == '__main__':
    main()
