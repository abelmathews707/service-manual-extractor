"""Bounded B2 extraction from explicit native rows/regions, never an approval.

Recipes choose structure and vocabulary, not expected answers. Original numbers
are read from source cells. Unsupported/OCR/composite values remain ambiguous.
Callers must establish the unit's vehicle scope before opening source content.
"""

import copy
import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path

from .applicability_contracts import POLICY_VERSION
from .contract import ContractError
from .html_content import Node, TreeParser, decode_html, text_of
from .matching import _alternative
from .structured_contracts import record_identity, seal_records
from .vehicle_interpretation import interpret_statement

VERSION = 'b2-native-rows-v1'
UNITS = {'Hz': ('frequency', 'Hz'), 'G/S': ('mass flow', 'g/s'),
         'V': ('voltage', 'V'), 'DCV': ('voltage', 'V'),
         'N.m': ('torque', 'N.m'), 'Nm': ('torque', 'N.m'),
         'N·m': ('torque', 'N.m'), 'lb-ft': ('torque', 'lb-ft'),
         'mm': ('length', 'mm'), 'in': ('length', 'in')}
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'
RANGE = re.compile(rf'({NUMBER})(?:\s*(?:-|to)\s*({NUMBER}))?')


@lru_cache(maxsize=1)
def extraction_revision():
    """Changing interpretation/layout/validation code changes record bindings."""
    root = Path(__file__).parent
    value = hashlib.sha256()
    for name in ('structured_extract.py', 'structured_contracts.py', 'html_content.py',
                 'vehicle_interpretation.py', 'matching.py'):
        value.update(name.encode() + b'\0' + (root / name).read_bytes())
    return VERSION + ':' + value.hexdigest()


def compact(text):
    return ' '.join(text.split())


def numeric_value(raw, unit):
    """No OCR repair, implicit conversion, slash splitting or unit guessing."""
    match = RANGE.fullmatch(raw.strip())
    if match is None or unit not in UNITS:
        return None
    low = float(match[1])
    high = float(match[2]) if match[2] else low
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        return None
    return {'minimum': low, 'maximum': high, 'unit': UNITS[unit][1]}


def _ancestor(node, tag):
    node = node.parent
    while node is not None:
        if node.tag == tag:
            return node
        node = node.parent
    return None


def table_grid(table):
    """Expand spans while retaining each cell's origin and original text."""
    rows = [node for node in table.walk()
            if node.tag == 'tr' and _ancestor(node, 'table') is table]
    if len(rows) > 2000 or any(node.tag == 'table' for node in table.walk() if node is not table):
        raise ContractError('nested/oversized tables need original-layout review')
    grid = {}
    for row_index, row in enumerate(rows):
        column = 0
        for cell in row.walk():
            if cell.tag not in ('td', 'th') or _ancestor(cell, 'tr') is not row:
                continue
            while (row_index, column) in grid:
                column += 1
            try:
                height, width = (int(cell.attrs.get(key, '1')) for key in ('rowspan', 'colspan'))
            except ValueError as error:
                raise ContractError('invalid table span') from error
            if not 1 <= height <= 64 or not 1 <= width <= 64 or row_index + height > len(rows):
                raise ContractError('table span exceeds row/column limits')
            item = {'text': compact(text_of(cell)), 'header': cell.tag == 'th',
                    'row': row_index, 'column': column}
            for y in range(row_index, row_index + height):
                for x in range(column, column + width):
                    if (y, x) in grid or x >= 64:
                        raise ContractError('overlapping/out-of-bounds table spans')
                    grid[y, x] = item
            column += width
    width = max((column + 1 for _, column in grid), default=0)
    if not width or any((row, column) not in grid
                        for row in range(len(rows)) for column in range(width)):
        raise ContractError('ragged table needs review; do not shift cells')
    return [[grid[row, column] for column in range(width)] for row in range(len(rows))], rows


def bound_record(kind, binding, vocabulary, configurations, locator, original,
                 payload, conditions=(), context=(), missing=()):
    result = {'type': kind, 'binding': copy.deepcopy(binding), 'locator': locator,
              'original_text': original, 'applicability': {
                  'vocabulary_revision': vocabulary['revision'], 'policy_version': POLICY_VERSION,
                  'configuration_ids': list(configurations)}, 'conditions': list(conditions),
              'context_record_ids': list(context), 'payload': payload,
              'completeness': {'state': 'ambiguous' if missing else 'complete',
                               'missing': list(missing)}}
    result['binding']['extraction_version'] = extraction_revision()
    result['id'] = record_identity(result)
    return result


def _scope(binding, configurations, decisions, *, allow_unmapped=False):
    if not configurations and not allow_unmapped:
        raise ContractError('B2 requires vehicle scope; unfiltered part review is explicit')
    for identifier in configurations:
        decision = decisions.get(identifier, {})
        if (decision.get('state') != 'confirmed' or
                decision.get('unit_id') != binding['unit_id'] or
                decision.get('configuration_id') != identifier):
            raise ContractError('B2 needs an exact confirmed unit/configuration before reading')


def _selector(node):
    parts = []
    while node.parent is not None:
        siblings = [item for item in node.parent.children
                    if isinstance(item, Node) and item.tag == node.tag]
        position = next(index for index, sibling in enumerate(siblings) if sibling is node)
        parts.append(f'{node.tag}:nth-of-type({position + 1})')
        node = node.parent
    return ' > '.join(reversed(parts))


def _row_scope(text, vocabulary, configurations):
    """Reuse correlated interpretation, and only narrow a confirmed parent.

Unresolved explicit vehicle cues cannot be inherited as universal row fitment.
This is a guard on reviewed recipes, not automatic approval of arbitrary rows.
"""
    alternatives, resolved = interpret_statement(text, vocabulary)
    has_constraint = any(item[field]['state'] != 'unknown' for item in alternatives
                         for field in ('make', 'model', 'year', 'engine'))
    has_vehicle_cue = re.search(r'\b(?:\d{1,2}(?:\.\d)?\s*L|VIN|RPO|Series|except|'
                                r'diesel|gasoline|CNG|(?:19|20)\d{2})\b', text, re.I)
    if not has_constraint and not has_vehicle_cue:
        return configurations
    if not resolved or not has_constraint:
        return []
    configs = {item['id']: item for item in vocabulary['configurations']}
    return [identifier for identifier in configurations if any(
        _alternative(alternative, configs[identifier])[0] != 'different'
        for alternative in alternatives)]


def extract_html(data, binding, vocabulary, configurations, decisions, recipes):
    """Extract selected rows from tables identified by their complete header paths.

Each recipe contains ``headers`` (one path per expanded column), ``rows``
(exact first-cell labels), value/condition columns, subject/optional identity
column, and optional caption/note text. Notes must occur uniquely outside a
table before the chosen table with no intervening table; never inherited across
all tables on a page. Recipes are bounded layout rules, not golden values.
    """
    _scope(binding, configurations, decisions)
    if binding['provenance'] != 'native':
        return seal_records([]), [{'reason': 'OCR tables need original-layout review'}]
    parser = TreeParser()
    parser.feed(decode_html(data, ford_legacy=True)[0])
    parser.close()
    nodes = list(parser.root.walk())
    positions = {id(node): index for index, node in enumerate(nodes)}
    tables = [node for node in nodes if node.tag == 'table']
    result, abstentions = [], []
    for recipe in recipes:
        candidates = []
        for index, table in enumerate(tables):
            try:
                grid, rows = table_grid(table)
            except ContractError:
                continue
            header_count = 0
            while header_count < len(grid) and all(cell['header'] for cell in grid[header_count]):
                header_count += 1
            paths = []
            for column in range(len(grid[0])):
                path = []
                for row in grid[:header_count]:
                    if row[column]['text'] and row[column]['text'] not in path:
                        path.append(row[column]['text'])
                paths.append(path)
            if paths == recipe['headers']:
                candidates.append((index, table, grid, rows, header_count))
        if len(candidates) != 1:
            abstentions.append({'recipe': recipe['name'],
                                'reason': 'table headers absent/ambiguous'})
            continue
        index, table, grid, rows, count = candidates[0]
        context = []
        context_failed = False
        for kind, text in [('region', recipe.get('caption')), ('warning', recipe.get('note'))]:
            if not text:
                continue
            found = [node for node in nodes if node.tag not in ('root', 'html', 'body', 'head')
                     and compact(text_of(node)) == text and
                     (_ancestor(node, 'table') is None or
                      kind == 'region' and _ancestor(node, 'table') is table)]
            found = [node for node in found if not any(
                compact(text_of(child)) == text for child in node.children
                if isinstance(child, Node))]
            inside_caption = (len(found) == 1 and kind == 'region' and
                              _ancestor(found[0], 'table') is table)
            if (len(found) != 1 or not inside_caption and (
                    positions[id(found[0])] >= positions[id(table)] or
                    any(positions[id(found[0])] < positions[id(other)] < positions[id(table)]
                        for other in tables))):
                context_failed = True
                break
            payload = ({'kind': 'table', 'caption_original': text} if kind == 'region'
                       else {'severity': 'note', 'instruction': text.removeprefix('NOTE: ')})
            record = bound_record(kind, binding, vocabulary, configurations,
                                  {'kind': 'text_quote', 'quote': text, 'prefix': '', 'suffix': ''},
                                  text, payload)
            context.append(record)
        if context_failed:
            abstentions.append({'recipe': recipe['name'], 'reason': 'governing context ambiguous'})
            continue
        header_text = compact(' '.join(text_of(row) for row in rows[:count]))
        header_record = bound_record('region', binding, vocabulary, configurations,
                                     {'kind': 'html', 'selector': _selector(table)},
                                     header_text, {'kind': 'table',
                                                   'caption_original': header_text})
        context.append(header_record)
        result.extend(context)
        for label in recipe['rows']:
            matches = [number for number in range(count, len(grid))
                       if grid[number][recipe.get('subject_column', 0)]['text'] == label]
            if len(matches) != 1:
                abstentions.append({'recipe': recipe['name'], 'row': label,
                                    'reason': 'row absent/ambiguous'})
                continue
            number = matches[0]
            if _row_scope(header_text + ' ' + recipe.get('caption', '') + ' ' + label,
                          vocabulary, configurations) != configurations:
                abstentions.append({'recipe': recipe['name'], 'row': label,
                                    'reason': 'conflicting/unresolved row vehicle restriction'})
                continue
            row = grid[number]
            unit = row[recipe['unit_column']]['text']
            values, missing = [], []
            for column, condition in recipe['value_columns']:
                if column >= len(row) or recipe['headers'][column][-1] != condition:
                    raise ContractError('operating condition must bind its original header')
                raw = row[column]['text']
                if not raw or not unit:
                    missing.append('empty value/unit; original required')
                    continue
                value = {'condition': condition, 'original_value': raw, 'original_unit': unit}
                normalized = numeric_value(raw, unit)
                if normalized is None:
                    missing.append(f'unsupported/ambiguous value or unit under {condition}')
                else:
                    value['normalized'] = normalized
                values.append(value)
            if not values:
                abstentions.append({'recipe': recipe['name'], 'row': label,
                                    'reason': 'no readable values; never substitute zero'})
                continue
            subject = recipe.get('subject_prefix', '') + label
            if recipe.get('identity_column') is not None:
                subject += (recipe.get('identity_prefix', ', ') +
                            row[recipe['identity_column']]['text'])
            subject += recipe.get('subject_suffix', '')
            quantity = UNITS.get(unit, ('unknown original quantity', None))[0]
            conditions = list(dict.fromkeys([item['condition'] for item in values] +
                                            recipe.get('conditions', [])))
            result.append(bound_record(
                'specification', binding, vocabulary, configurations,
                {'kind': 'html', 'selector': _selector(rows[number])},
                compact(text_of(rows[number])),
                {'subject': subject, 'quantity': quantity, 'values': values}, conditions,
                [item['id'] for item in context], list(dict.fromkeys(missing))))
    unique = {record['id']: record for record in result}
    if len(unique) != len(result):
        raise ContractError('recipes overlap; review extraction instead of overwriting records')
    return seal_records(result), abstentions


def extract_part_mentions(text, binding, vocabulary, configurations, decisions,
                          *, pattern, namespace, allow_unmapped=False):
    """Printed identifier proposals only. No inferred fitment/supersession."""
    _scope(binding, configurations, decisions, allow_unmapped=allow_unmapped)
    if not namespace.strip():
        raise ContractError('printed identifiers require a declared namespace')
    if binding['provenance'] != 'native':
        return seal_records([]), [{'reason': 'OCR identifiers need original review'}]
    result = []
    for line in text.splitlines():
        original = compact(line)
        for match in re.finditer(pattern, original):
            identifier = match[0]
            if not identifier or text.count(identifier) != 1:
                continue
            result.append(bound_record('part_reference', binding, vocabulary, configurations,
                                       {'kind': 'text_quote', 'quote': original,
                                        'prefix': '', 'suffix': ''}, original,
                                       {'identifier_original': identifier,
                                        'namespace': namespace, 'relationship': 'mentioned'}))
    return seal_records(result), []


def pdf_region_text(path, page, bbox):
    """Read selectable native text only in an explicitly reviewed PDF region.

No OCR fallback. Rectangles are fractional page coordinates and must not clip
any intersecting word. PDF layout review remains required before approval.
"""
    try:
        import pymupdf
    except ImportError as error:
        raise ContractError('native PDF region extraction requires PyMuPDF') from error
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ContractError('invalid PDF region')
    with pymupdf.open(path) as document:
        if not 1 <= page <= len(document):
            raise ContractError('PDF page absent')
        item = document[page - 1]
        region = pymupdf.Rect(x0 * item.rect.width, y0 * item.rect.height,
                              x1 * item.rect.width, y1 * item.rect.height)
        for word in item.get_text('words'):
            rectangle = pymupdf.Rect(word[:4])
            if rectangle.intersects(region) and not region.contains(rectangle):
                raise ContractError('PDF region clips a word; expand/review region')
        return item.get_text('text', clip=region, sort=True).strip()


def extract_native_line(text, binding, vocabulary, configurations, decisions,
                        *, locator, pattern, condition):
    """Explicit full-region grammar with subject/value/unit named groups.

Only one clear native measurement. Tables/figures, multiple values, comparisons,
warnings and branch instructions need a different reviewed layout rule.
"""
    _scope(binding, configurations, decisions)
    original = compact(text)
    match = re.fullmatch(pattern, original)
    if binding['provenance'] != 'native' or match is None:
        return seal_records([]), [{'reason': 'OCR/ambiguous native region; no typed value'}]
    subject, raw, unit = (match[name] for name in ('subject', 'value', 'unit'))
    normalized = numeric_value(raw, unit)
    if normalized is None:
        return seal_records([]), [{'reason': 'unsupported numeric value/unit'}]
    record = bound_record('specification', binding, vocabulary, configurations, locator,
                          original, {'subject': subject, 'quantity': UNITS[unit][0],
                                     'values': [{'condition': condition, 'original_value': raw,
                                                 'original_unit': unit,
                                                 'normalized': normalized}]}, [condition],
                          missing=[] if condition in original else [
                              'operating condition absent from native region; '
                              'original context required'])
    return seal_records([record]), []
