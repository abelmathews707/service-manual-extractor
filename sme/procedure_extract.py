"""B3 native decision extraction; explicit continuations never imply approval.

Only reviewed structural shapes are supported. Each decision retains its source
instructions and both printed alternatives. Unresolved prerequisites, references
and conditional alternatives stay incomplete. This module does not fetch links.
"""

import hashlib
import re
from pathlib import Path

from .contract import ContractError
from .html_content import Node, TreeParser, decode_html, text_of
from .structured_contracts import record_identity, seal_records
from .structured_extract import (
    _row_scope,
    _scope,
    _selector,
    bound_record,
    compact,
    extraction_revision,
    table_grid,
)


def _record(kind, binding, vocabulary, configurations, locator, original, payload,
            *, context=(), missing=()):
    item = bound_record(kind, binding, vocabulary, configurations, locator, original,
                        payload, context=context, missing=missing)
    revision = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    item['binding']['extraction_version'] = 'b3-native-decisions-v1:' + revision + ':' + \
        extraction_revision()
    if missing:
        item['completeness']['state'] = 'incomplete'
    item['id'] = record_identity(item)
    return item


def _quote(text):
    return {'kind': 'text_quote', 'quote': text, 'prefix': '', 'suffix': ''}


def _graph(binding, vocabulary, configurations, question, question_locator,
           branches, context, missing):
    records = list(context)
    missing = list(missing)
    if any(item['completeness']['state'] != 'complete' for item in context):
        missing.append('Required instruction context is incomplete')
    context_ids = [item['id'] for item in context]
    decision = _record('diagnostic_node', binding, vocabulary, configurations,
                       question_locator, question,
                       {'node_kind': 'decision', 'operation': question,
                        'expected_results': [], 'required_branch_labels': ['Yes', 'No']},
                       context=context_ids, missing=missing)
    records.append(decision)
    continuations = []
    for label, original, locator, links in branches:
        # Text can name a continuation even when the source has no hyperlink.
        unresolved = bool(links or re.search(
            r'\b(?:go\s+to|proceed|repeat|refer\s+to|next\s+step|see\s+)', original, re.I))
        branch_missing = list(missing)
        if unresolved:
            branch_missing.append(
                'Continuation requires independent source, vehicle and quality review')
        outcome = _record('diagnostic_node', binding, vocabulary, configurations,
                          locator, original,
                          {'node_kind': 'outcome', 'operation': original,
                           'expected_results': [], 'required_branch_labels': []},
                          context=context_ids, missing=branch_missing)
        edge = _record('diagnostic_edge', binding, vocabulary, configurations,
                       locator, original,
                       {'from_record_id': decision['id'], 'to_record_id': outcome['id'],
                        'label': label, 'condition': label + ': ' + question},
                       missing=branch_missing)
        records.extend((outcome, edge))
        if unresolved:
            continuations.append({'record_id': outcome['id'], 'label': label,
                                  'source_unit_id': binding['unit_id'],
                                  'targets': links, 'state': 'unresolved'})
            decision['completeness'] = {'state': 'incomplete', 'missing': sorted(set(
                decision['completeness']['missing'] + branch_missing))}
    return seal_records(records), continuations


def extract_html_decision(data, binding, vocabulary, configurations, decisions, *,
                          anchor, missing_context=(), allow_unmapped=False):
    """Read one anchored HTML test with exactly one question and Yes/No table.

    Unmapped original inspection is explicit and produces no vehicle eligibility.
    The caller supplies missing prerequisites based on original review. No source
    hyperlinks are followed. Source list items are retained as context rather
    than assumed to be unconditional ordered instructions.
    """
    _scope(binding, configurations, decisions, allow_unmapped=allow_unmapped)
    if binding['provenance'] != 'native':
        raise ContractError('OCR procedure extraction requires original-layout review')
    parser = TreeParser()
    parser.feed(decode_html(data, ford_legacy=True)[0])
    parser.close()
    nodes = list(parser.root.walk())
    starts = [i for i, node in enumerate(nodes)
              if node.attrs.get('name') == anchor or node.attrs.get('id') == anchor]
    if len(starts) != 1:
        raise ContractError('procedure anchor is missing or duplicated')
    start = starts[0]
    end = next((i for i in range(start + 1, len(nodes))
                if nodes[i].tag == 'a' and nodes[i].attrs.get('name')), len(nodes))
    section = nodes[start + 1:end]
    headings = [node for node in section if node.tag in ('h3', 'h4')]
    questions = [node for node in section if node.attrs.get('class', '').lower() == 'question']
    if len(headings) != 1 or len(questions) != 1:
        raise ContractError('procedure heading/question is missing or ambiguous')
    question = questions[0]
    if configurations and not _row_scope(compact(text_of(question)), vocabulary, configurations):
        raise ContractError('question contains conflicting/unresolved vehicle restrictions')
    question_index = next(i for i, node in enumerate(section) if node is question)
    after = section[question_index + 1:]
    tables = [node for node in after if node.tag == 'table']
    if len(tables) != 1:
        raise ContractError('procedure must contain exactly one branch table')
    grid, rows = table_grid(tables[0])
    if len(grid) != 2 or len(grid[0]) != 2 or \
            [cell['text'].casefold() for cell in grid[0]] != ['yes', 'no'] or \
            any(not cell['header'] for cell in grid[0]) or \
            any(not cell['text'] or cell['column'] != i or cell['row'] != 1
                for i, cell in enumerate(grid[1])):
        raise ContractError('missing, merged or unsupported Yes/No branches')
    before = section[:question_index]
    # Top-level instruction containers retain nested notes and qualifiers verbatim.
    selected = []
    for node in before:
        if node.tag not in ('ul', 'ol', 'p') or not compact(text_of(node)):
            continue
        parent = node.parent
        if any(parent is chosen or any(child is node for child in chosen.walk())
               for chosen in selected):
            continue
        selected.append(node)
    context = []
    missing = list(missing_context)
    if not configurations:
        missing.append('Vehicle applicability has not been established')
    for node in [headings[0], *selected]:
        original = compact(text_of(node))
        if configurations and not _row_scope(original, vocabulary, configurations):
            raise ContractError('procedure contains conflicting/unresolved vehicle restrictions')
        if node is headings[0]:
            context.append(_record('region', binding, vocabulary, configurations,
                                   {'kind': 'html', 'selector': _selector(node)}, original,
                                   {'kind': 'table', 'caption_original': original}))
        else:
            grouping = 'Instruction grouping requires ordered-step review'
            context.append(_record('procedure_step', binding, vocabulary, configurations,
                                   {'kind': 'html', 'selector': _selector(node)}, original,
                                   {'sequence': len(context), 'instruction': original,
                                    'tool_ids': [], 'next_record_ids': []}, missing=[grouping]))
            missing.append(grouping)
        if any(child.tag == 'a' and child.attrs.get('href') for child in node.walk()) or \
                re.search(r'\b(?:refer\s+to|see\s+|manufacturer.s\s+instruction)', original, re.I):
            missing.append('Instruction context contains an unreviewed reference')
    cells = [child for child in rows[1].children if isinstance(child, Node)
             and child.tag in ('td', 'th')]
    if len(cells) != 2:
        raise ContractError('branch cells require layout review')
    branches = []
    for label, cell in zip(('Yes', 'No'), cells):
        text = compact(text_of(cell))
        if configurations and not _row_scope(text, vocabulary, configurations):
            raise ContractError('branch contains conflicting/unresolved vehicle restrictions')
        branches.append((label, text, {'kind': 'html', 'selector': _selector(cell)},
                         [node.attrs['href'] for node in cell.walk()
                          if node.tag == 'a' and node.attrs.get('href')]))
    return _graph(binding, vocabulary, configurations, compact(text_of(question)),
                  {'kind': 'html', 'selector': _selector(question)}, branches, context, missing)


def extract_native_decision(text, binding, vocabulary, configurations, decisions, *,
                            locator, context=(), missing_context=()):
    """Parse an entire native numbered step ending in explicit If yes/If no text.

    Region selection/word-clipping checks happen before this function. All supplied
    context records must be source-validated alongside the result by the caller.
    """
    _scope(binding, configurations, decisions)
    if binding['provenance'] != 'native':
        raise ContractError('OCR procedure extraction requires original-layout review')
    text = compact(text)
    match = re.fullmatch(r'(\d+)\. (.+?\?) (If yes, (.+?)\.?) (If no, (.+))', text, re.I)
    if (match is None or text.count('?') != 1 or text.lower().count('if yes,') != 1 or
            text.lower().count('if no,') != 1):
        raise ContractError('native step has missing or ambiguous conditional branches')
    if not _row_scope(text, vocabulary, configurations):
        raise ContractError('native step has conflicting/unresolved vehicle restrictions')
    parts = re.fullmatch(r'(.*?)(\b(?:Does|Do|Is|Are|Did|Has|Have|Can)\b.+\?)', match[2])
    if parts is None:
        raise ContractError('native step question cannot be separated without inference')
    instruction, question = parts[1].strip(), parts[2]
    if not instruction:
        raise ContractError('native numbered step has no explicit operation')
    missing = list(missing_context)
    if not context:
        missing.append('Governing warnings and prerequisites have not been reviewed')
    step = _record('procedure_step', binding, vocabulary, configurations, locator, text,
                   {'sequence': int(match[1]), 'instruction': instruction,
                    'tool_ids': [], 'next_record_ids': []},
                   context=[item['id'] for item in context],
                   missing=sorted(set(missing + [
                       'Conditional continuation is represented by the decision graph'])))
    return _graph(binding, vocabulary, configurations, question, _quote(question),
                  [('Yes', match[3], _quote(match[3]), []),
                   ('No', match[5], _quote(match[5]), [])], [*context, step], missing)
