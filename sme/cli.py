"""Manufacturer-neutral command line for source inspection and extraction."""

import argparse
import json
import sys

from . import __version__
from .contract import ContractError, contract_summary, load_manifest
from .discovery import discover_folder
from .evidence import write_evidence
from .ford_adapter import import_ford, probe_ford
from .normalize import normalize_source
from .ocr_selection import plan_ocr, run_toolkit_ocr
from .orchestrate import process_folder
from .source import SourceError, extract_source, inspect_source
from .viewer import build_viewer


def cmd_contract(args):
    value = contract_summary()
    if args.json:
        print(json.dumps(value, indent=2))
    else:
        print(f'Manifest contract: {value["manifest_contract"]}')
        print(f'Operation contract: {value["operation_contract"]}')
        print('Declared formats: ' + ', '.join(value['formats']))
        print('Neutral readers: ' + ', '.join(value['neutral_readers']))
    return 0


def _print_operation(value):
    source = value['source']
    print(f'Format: {source["format"]}')
    print(f'Container: {source["container"]}')
    print(f'Status: {source["status"]}')
    print(f'Source ID: {source["id"]}')
    print(f'Publications: {len(value["publications"])}')
    for publication in value['publications']:
        print(f'  {publication["id"]}  {publication["source_path"]}')
    for diagnostic in value['diagnostics']:
        print(f'{diagnostic["level"]}: {diagnostic["message"]}', file=sys.stderr)
    if value['operation'] == 'extract' and value['output']:
        output = value['output']
        print(f'Files written: {output["files_written"]}')
        print(f'Bytes written: {output["bytes_written"]}')


def _source_error(args, error):
    if args.json:
        print(json.dumps({'ok': False, 'error': str(error)}, indent=2))
    else:
        print(f'error: {error}', file=sys.stderr)
    return 2


def cmd_probe(args):
    try:
        value = inspect_source(args.source).operation()
    except (OSError, SourceError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        _print_operation(value)
    return 0 if value['ok'] else 1


def cmd_extract(args):
    try:
        value = extract_source(
            args.source,
            args.out,
            publication_ids=args.publication,
        )
    except (OSError, SourceError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        _print_operation(value)
    return 0 if value['ok'] else 1


def cmd_validate(args):
    try:
        value = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ContractError) as ex:
        if args.json:
            print(json.dumps({'ok': False, 'error': str(ex)}, indent=2))
        else:
            print(f'error: {ex}', file=sys.stderr)
        return 1
    result = {
        'ok': True,
        'contract': value['contract'],
        'source_id': value['source']['id'],
        'publications': len(value['publications']),
        'documents': sum(len(item['documents']) for item in value['publications']),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f'{args.manifest}: valid {value["contract"]}')
    return 0


def cmd_normalize(args):
    try:
        result = normalize_source(args.source, args.out, args.ocr_manifest, args.source_inventory)
    except (OSError, SourceError, ContractError, json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f'Normalization: {result["status"]}')
        print(f'Documents: {result["documents"]}; searchable: {result["searchable_documents"]}')
        print(f'Output: {result["output"]}')
        for failure in result['failures']:
            print(f'{failure["path"]}: {failure["message"]}', file=sys.stderr)
    return 0 if result['ok'] else 1


def cmd_build_viewer(args):
    try:
        result = build_viewer(args.source, args.out, args.title)
    except (OSError, SourceError, ContractError, json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f'Viewer: {result["publications"]} publications, {result["documents"]} documents')
        print(f'Output: {result["output"]}')
        if result['content_status'] != 'complete':
            print(
                'Warning: normalized content is partial; unavailable material is labeled.',
                file=sys.stderr,
            )
    return 0


def cmd_ford_probe(args):
    try:
        value = probe_ford(args.source)
    except (OSError, SourceError, ValueError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        for item in value['archives']:
            print(
                f'{item["identity"]}  POD v{item["version"]}  '
                f'{item["type"] or "unknown"}  {item["title"]}'
            )
    return 0


def cmd_ford_import(args):
    try:
        value = import_ford(args.source, args.out, args.archive)
    except (OSError, SourceError, ValueError, ContractError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(
            f'{value["publications"]} Ford publications, '
            f'{value["documents"]} documents: {value["output"]}'
        )
        if value['failures']:
            print(
                f'Warning: {len(value["failures"])} normalization failures; '
                'see the capability report.',
                file=sys.stderr,
            )
    return 0 if not value['failures'] else 1


def cmd_discover(args):
    try:
        value = discover_folder(args.folder)
    except (OSError, SourceError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        for item in value['sources']:
            print(f"{item['status']:11} {item['name']}  "
                  f"{item['route'] or item['reason'] or ''}")
    return 0 if not value['counts']['failed'] else 1


def cmd_evidence(args):
    try:
        value = write_evidence(args.package, args.vocabulary, args.out)
    except (OSError, SourceError, ValueError, ContractError,
            json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(f"{value['units']} evidence units, {value['assertions']} source statements: "
              f"{value['output']}")
    return 0


def cmd_plan_ocr(args):
    try:
        value = plan_ocr(args.package, args.low_text_chars)
    except (OSError, SourceError, ValueError, ContractError,
            json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        for item in value['publications']:
            print(f"{item['source_path']}: {len(item['auto_pages'])} automatic image-only, "
                  f"{len(item['review_pages'])} pages needing review")
    return 0


def cmd_toolkit_ocr(args):
    try:
        value = run_toolkit_ocr(args.package, args.source_path, args.toolkit,
                                args.cache, args.approve_page or ())
    except (OSError, SourceError, ValueError, ContractError,
            json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(f"OCR pages {value['pages']}: {value['ocr_map']}")
        if value.get('pages_without_ocr_text'):
            print('Warning: selected pages still have no text after OCR.', file=sys.stderr)
    return 0


def cmd_process_folder(args):
    selections = {}
    for item in args.ford_archive or ():
        name, separator, identity = item.partition(':')
        if not separator or not name or not identity:
            return _source_error(args, SourceError(
                '--ford-archive must be CHILD:content/locale/book.arc'))
        selections.setdefault(name, []).append(identity)
    try:
        value = process_folder(args.folder, args.out, args.include, selections)
    except (OSError, SourceError, ValueError, ContractError,
            json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        for item in value['results']:
            print(f"{item['name']}: {item['status']}, {len(item['packages'])} package(s)")
        if value['unsupported']:
            print('Unsupported or partial: ' + ', '.join(value['unsupported']),
                  file=sys.stderr)
    return 0


def make_parser():
    parser = argparse.ArgumentParser(
        prog='sme',
        description='Safely inspect and extract supported service-manual sources.',
        epilog='Normalize a verified extraction to preserve HTML structure and cited PDF pages.',
    )
    parser.add_argument('--version', action='version', version=f'sme {__version__}')
    commands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')

    command = commands.add_parser('contract', help='show the supported contract vocabulary')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_contract)

    command = commands.add_parser('validate-manifest', help='validate a v1 manifest JSON file')
    command.add_argument('manifest')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_validate)

    command = commands.add_parser(
        'probe',
        help='inspect a ZIP, folder or PDF without writing output',
    )
    command.add_argument('source')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_probe)

    command = commands.add_parser(
        'extract',
        help='verify and atomically copy selected original files',
    )
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument(
        '--publication',
        action='append',
        help='exact publication ID to extract (repeatable; default: all)',
    )
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_extract)

    command = commands.add_parser('ford-probe', help='list exact Ford POD archive identities')
    command.add_argument('source')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_ford_probe)

    command = commands.add_parser('ford-import', help='import selected Ford POD archives')
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument(
        '--archive',
        action='append',
        required=True,
        help='exact source-relative archive identity (repeatable)',
    )
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_ford_import)

    command = commands.add_parser('discover', help='inventory a mixed outer manual folder')
    command.add_argument('folder')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_discover)

    command = commands.add_parser('emit-evidence',
                                  help='capture source statements as unconfirmed proposals')
    command.add_argument('package', help='normalized source package')
    command.add_argument('--vocabulary', required=True,
                         help='vehicle-vocabulary/v1 JSON file')
    command.add_argument('-o', '--out', required=True)
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_evidence)

    command = commands.add_parser('plan-ocr',
                                  help='flag image-only and low-text PDF pages before OCR')
    command.add_argument('package', help='normalized source package')
    command.add_argument('--low-text-chars', type=int, default=80)
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_plan_ocr)

    command = commands.add_parser('toolkit-ocr',
                                  help='OCR only selected PDF pages with the local toolkit')
    command.add_argument('package', help='normalized source package')
    command.add_argument('--source-path', required=True,
                         help='exact original PDF path from plan-ocr')
    command.add_argument('--toolkit', required=True,
                         help='independent workshop-manual-toolkit checkout')
    command.add_argument('--cache', required=True,
                         help='existing local output/cache directory')
    command.add_argument('--approve-page', action='append', type=int,
                         help='explicitly approve a review page for OCR (repeatable)')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_toolkit_ocr)

    command = commands.add_parser('process-folder',
                                  help='route a mixed outer folder into cached packages')
    command.add_argument('folder')
    command.add_argument('-o', '--out', required=True,
                         help='new or existing local cache directory outside the source')
    command.add_argument('--include', action='append',
                         help='immediate child name to process (repeatable; default all)')
    command.add_argument('--ford-archive', action='append',
                         help='CHILD:exact/source-relative.arc selection (repeatable)')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_process_folder)

    command = commands.add_parser('normalize', help='normalize a verified Step 3 extraction')
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument('--ocr-manifest', help='hash-bound service-manual-ocr-map/v1 JSON')
    command.add_argument('--source-inventory', help='full same-source inventory for excluded links')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_normalize)

    command = commands.add_parser(
        'build-viewer',
        help='build the shared offline viewer from a normalized package',
    )
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument('--title', help='override the library title')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_build_viewer)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    return args.function(args)
