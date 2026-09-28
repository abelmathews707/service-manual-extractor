"""Publish B1 into a new disposable library; keep accepted A10 outputs intact."""

import argparse
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from sme.library_export import publish_library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accepted_generation', type=Path)
    parser.add_argument('acceptance_root', type=Path)
    args = parser.parse_args()
    sources = []
    for item in read(args.accepted_generation / 'library.json')['packages']:
        sources.append({'package': str(args.accepted_generation / item['root']),
                        'evidence': read(args.acceptance_root / 'evidence' /
                                         (item['source_id'] + '.json'))})
    result = publish_library(str(args.acceptance_root / 'library'), sources,
                             read(args.acceptance_root / 'vocabulary.json'),
                             read(args.acceptance_root / 'review.json'),
                             progress=lambda event: print(json.dumps(event), flush=True))
    write_once(args.acceptance_root / 'publication.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
