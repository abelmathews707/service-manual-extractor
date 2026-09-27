"""Publish the reviewed A10 Ford/GM pilot into a disposable local library."""

import argparse
import json

from sme.library_export import publish_library


def _read(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ford-package', required=True)
    parser.add_argument('--ford-evidence', required=True)
    parser.add_argument('--gm-package', required=True)
    parser.add_argument('--gm-evidence', required=True)
    parser.add_argument('--vocabulary', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = publish_library(args.output, [
        {'package': args.ford_package, 'evidence': _read(args.ford_evidence)},
        {'package': args.gm_package, 'evidence': _read(args.gm_evidence)},
    ], _read(args.vocabulary), _read(args.review))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
