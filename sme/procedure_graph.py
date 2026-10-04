"""Bounded graph-completeness audit, not execution or diagnostic approval.

Callers validate records against their originals and resolve vehicle scope first.
This module does no I/O, follows no manual links, evaluates no free-text condition,
and cannot convert reference-only source paths into executable branches.
"""

from .contract import ContractError


def graph_completeness(record_id, records):
    """Inspect the full bound dependency closure, retaining finite repeat cycles.

    A cycle is not itself an error: an explicit reviewed repeat may have an exit.
    A flow component with no reachable terminal is incomplete. Reachability does
    not assert that a condition is satisfiable or that a procedure terminates for
    every real vehicle; those judgments still require independent original review.
    """
    # Local import keeps the quality validator able to invoke the same check.
    from .structured_contracts import dependency_bindings, record_digest, record_identity

    index = {record['id']: record for record in records}
    if len(index) != len(records) or record_id not in index:
        raise ContractError('graph requires distinct records and a present starting record')
    closure = dependency_bindings(record_id, records)
    selected = {item['record_id']: index[item['record_id']] for item in closure}
    if any(record_identity(item) != identifier or
           record_digest(item) != item['record_sha256'] for identifier, item in selected.items()):
        raise ContractError('graph record identity or content changed')
    problems = []

    def problem(identifier, reason):
        value = {'record_id': identifier, 'reason': reason}
        if value not in problems:
            problems.append(value)

    flow = {identifier: set() for identifier, item in selected.items()
            if item['type'] in ('procedure_step', 'diagnostic_node')}
    terminals = set()
    for identifier, item in selected.items():
        if item['completeness']['state'] != 'complete':
            for reason in item['completeness']['missing'] or ['Record is incomplete']:
                problem(identifier, reason)
        payload = item['payload']
        if item['type'] == 'procedure_step':
            flow[identifier].update(payload['next_record_ids'])
            if payload.get('source_paths'):
                problem(identifier, 'Conditional source references are not reviewed graph edges')
            if payload.get('substep_record_ids') or payload.get('parent_record_id'):
                problem(identifier, 'Printed step hierarchy has no reviewed execution order')
            if not payload['next_record_ids']:
                terminals.add(identifier)
        elif item['type'] == 'diagnostic_node':
            edges = [edge for edge in selected.values() if edge['type'] == 'diagnostic_edge'
                     and edge['payload']['from_record_id'] == identifier]
            labels = [edge['payload']['label'] for edge in edges]
            expected = payload['required_branch_labels']
            if set(labels) != set(expected) or len(labels) != len(set(labels)):
                problem(identifier, 'A required diagnostic branch is missing or duplicated')
            flow[identifier].update(edge['payload']['to_record_id'] for edge in edges)
            if payload['node_kind'] == 'outcome':
                if edges or expected:
                    problem(identifier, 'A terminal outcome has outgoing diagnostic branches')
                else:
                    terminals.add(identifier)
            elif not edges:
                problem(identifier, 'Nonterminal diagnostic node has no next branch')
            if payload['node_kind'] == 'decision' and len(set(expected)) < 2:
                problem(identifier, 'A decision needs separately represented alternatives')
            if payload['node_kind'] == 'test' and not payload['expected_results']:
                problem(identifier, 'A diagnostic test has no expected readings')

    # Backward reachability is cycle-safe and does not guess how often to repeat.
    can_finish = set(terminals)
    pending = list(terminals)
    reverse = {identifier: set() for identifier in flow}
    for identifier, targets in flow.items():
        for target in targets:
            if target not in reverse:
                raise ContractError('graph edge has an absent or non-flow target')
            reverse[target].add(identifier)
    while pending:
        for identifier in reverse[pending.pop()] - can_finish:
            can_finish.add(identifier)
            pending.append(identifier)
    for identifier in sorted(set(flow) - can_finish):
        problem(identifier, 'No explicit terminal is reachable from this flow component')
    return {'state': 'incomplete' if problems else 'complete',
            'root_record_id': record_id, 'dependency_bindings': closure,
            'flow_records': len(flow),
            'flow_edges': sum(len(targets) for targets in flow.values()),
            'terminal_record_ids': sorted(terminals), 'problems': problems,
            'assessment': 'Bounded structural check, not original-review or diagnostic approval',
            'diagnostic_ready': False}
