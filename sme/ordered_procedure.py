"""Bounded native ordered-list extraction using original-reviewed DOM recipes.

Printed order is not unconditional execution order. Nested, conditional or linked
steps preserve their entire text and stay incomplete instead of invented graphs.
"""

import hashlib
import re
from pathlib import Path

from .contract import ContractError
from .html_content import Node, TreeParser, decode_html, text_of
from .procedure_extract import _record
from .structured_contracts import seal_records
from .structured_extract import _row_scope, _scope, _selector, compact


def extract_html_ordered_steps(data, binding, vocabulary, configurations, decisions, *,
                               list_selectors, context=(), required_tools=(),
                               coverage_reviewed=False, missing_context=(), ford_legacy=False):
    """Extract decimal OL/LI order, required tool quotations and supplied context.

    Recipes name source DOM selectors, not expected instruction text. Each required
    tool is ``(selector, operation_quote)``; the operation must also occur in this
    original. Callers must compare context/tool coverage before setting
    ``coverage_reviewed``. This asserts recipe coverage only, never content approval.
    ``context`` uses the existing source-bound warning/region records.
    """
    _scope(binding, configurations, decisions)
    if binding['provenance'] != 'native':
        raise ContractError('OCR ordered steps require original-layout review')
    if type(coverage_reviewed) is not bool:
        raise ContractError('coverage review must be explicit boolean')
    parser = TreeParser()
    parser.feed(decode_html(data, ford_legacy=ford_legacy)[0])
    parser.close()
    nodes = list(parser.root.walk())
    selectors = {_selector(node): node for node in nodes if node.parent is not None}
    if not list_selectors or len(list_selectors) != len(set(list_selectors)):
        raise ContractError('ordered extraction requires distinct source lists')

    def select(selector):
        if selector not in selectors:
            raise ContractError('ordered procedure source selector is missing')
        node = selectors[selector]
        if not compact(text_of(node)):
            raise ContractError('ordered procedure source selector is empty')
        return node

    selected = [select(selector) for selector in list_selectors]
    positions = [next(i for i, node in enumerate(nodes) if node is chosen) for chosen in selected]
    if positions != sorted(positions):
        raise ContractError('recipe order differs from the original document')
    missing = list(missing_context)
    if not coverage_reviewed:
        missing.append('Prerequisite, context and tool coverage require original review')
    if any(item['completeness']['state'] != 'complete' for item in context):
        missing.append('Required source context is incomplete')
    version = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def record(kind, node, payload, *, context_ids=(), problems=()):
        original = compact(text_of(node))
        if not _row_scope(original, vocabulary, configurations):
            raise ContractError('ordered procedure has conflicting/unresolved vehicle restrictions')
        value = _record(kind, binding, vocabulary, configurations,
                        {'kind': 'html', 'selector': _selector(node)}, original, payload,
                        context=context_ids, missing=problems)
        value['binding']['extraction_version'] = 'b3-ordered-v1:' + version + ':' + \
            value['binding']['extraction_version']
        return value

    tools = []
    full_text = compact(text_of(parser.root))
    for item in context:
        if (item['binding']['unit_id'] != binding['unit_id'] or
                item['binding']['source_id'] != binding['source_id'] or
                item['original_text'] not in full_text or
                not set(configurations) <= set(item['applicability']['configuration_ids']) or
                not _row_scope(item['original_text'], vocabulary, configurations)):
            raise ContractError('ordered context does not belong to the selected source/vehicle')
    for selector, operation in required_tools:
        if not isinstance(operation, str) or not operation.strip() or operation not in full_text:
            raise ContractError('required tool operation must be an exact original quotation')
        node = select(selector)
        tools.append(record('tool', node, {'name': compact(text_of(node)),
                                          'required_operation': operation}))
    if len({item['id'] for item in tools}) != len(tools):
        raise ContractError('required tools contain duplicate selectors')
    steps = []
    expected = 1
    for container in selected:
        if container.tag != 'ol' or container.attrs.get('type', '1') != '1' or \
                'reversed' in container.attrs:
            raise ContractError('only explicit forward decimal ordered lists are supported')
        parent = container.parent
        while parent is not None:
            if parent.tag in ('ol', 'ul', 'li'):
                raise ContractError('nested lists cannot be promoted to independent root steps')
            parent = parent.parent
        start = container.attrs.get('start', '1')
        if not start.isdecimal() or int(start) != expected:
            raise ContractError('printed step order has a gap, reset or unsupported start')
        children = [node for node in container.children if isinstance(node, Node)]
        if not children or any(node.tag != 'li' for node in children) or any(
                isinstance(node, str) and node.strip() for node in container.children):
            raise ContractError('ordered list contains unassigned instruction content')
        for node in children:
            number = node.attrs.get('value', str(expected))
            if not number.isdecimal() or int(number) != expected:
                raise ContractError('printed step order has a gap or repeated number')
            original = compact(text_of(node))
            if not original:
                raise ContractError('ordered step is empty')
            descendants = list(node.walk())
            if any(child.tag in ('img', 'svg', 'object') for child in descendants):
                missing.append('Step figure/diagram requires bound context review')
            if any(child.tag in ('ol', 'ul') for child in descendants):
                missing.append('Nested step hierarchy requires separate branch/order review')
            if any(child.tag == 'a' and child.attrs.get('href') for child in descendants) or \
                    re.search(r'\b(?:if|unless|otherwise|repeat|rerun|refer\s+to|go\s+to|'
                              r'proceed|see\s+|M/T|A/T)\b', original, re.I):
                missing.append('Conditional or linked step requires separate continuation review')
            steps.append(record('procedure_step', node,
                                 {'sequence': expected, 'instruction': original,
                                  'tool_ids': [item['id'] for item in tools],
                                  'next_record_ids': []},
                                 context_ids=[item['id'] for item in context]))
            expected += 1
    # Only flat unconditional sequences receive next edges. Keep the printed
    # sequence for all others, without implying every alternative must be executed.
    if missing:
        for step in steps:
            step['completeness'] = {'state': 'incomplete', 'missing': sorted(set(missing))}
    else:
        for step, following in zip(steps, steps[1:]):
            step['payload']['next_record_ids'] = [following['id']]
    return seal_records([*context, *tools, *steps])
