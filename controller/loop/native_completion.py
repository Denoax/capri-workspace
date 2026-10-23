"""Shared native completion evidence; never grants dispatch or acceptance authority."""
import json
from pathlib import Path
from .util import Rejected, atomic, identity, redact, tree, write_json


def validation_failure(receipt):
    return 'FAILED' if receipt.get('validation_failed') and receipt.get('effects_accounted') else 'DISPATCH_UNCERTAIN'


def retain_execution(receipt, lifecycle, binding, capture, workspace, before, allowed, independent_checks):
    """Capture observable execution/effects before parsing or validating model output.

    Unknown children, incomplete tools, scope drift and missing capture stay uncertain.
    The persistent backend's liveness is not a completion signal.
    """
    after = tree(workspace)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    records = [json.loads(line) for line in (Path(capture)/'events.jsonl').read_text().splitlines()]
    messages = [r['message'] for r in records if r.get('role') == binding.role and r.get('generation') == binding.generation]
    terminal = [m for m in messages if m.get('method') == 'turn/completed']
    matching = len(terminal) == 1 and terminal[0]['params'].get('threadId') == binding.thread and terminal[0]['params']['turn'].get('id') == lifecycle.turn
    from .native_protocol import Lifecycle
    replay = Lifecycle(binding.thread)
    try:
        for message in messages:
            replay.feed(message)
        replay.finish(lambda _: True, lambda: True)
        capture_accounted = (replay.turn == lifecycle.turn and replay.tools == lifecycle.tools
                             and replay.items == lifecycle.items and replay.final == lifecycle.final)
    except (ValueError, TypeError, KeyError):
        capture_accounted = False
    tools_accounted = True
    for m in messages:
        if m.get('method') != 'item/completed':
            continue
        item = m.get('params', {}).get('item', {})
        if item.get('type') == 'commandExecution':
            tools_accounted &= item.get('status') == 'completed' and type(item.get('exitCode')) is int
    complete = lifecycle.thread == binding.thread and lifecycle.started and lifecycle.turn and lifecycle.terminal == 'completed' and not lifecycle.failure and all(done for _, done in lifecycle.items.values())
    receipt.update(source_before=identity(before), source_after=identity(after), changed_paths=changed,
        scope=sorted(allowed), terminal=terminal, tool_items=sorted(lifecycle.tools),
        effects_accounted=bool(complete and matching and capture_accounted and tools_accounted and set(changed) <= set(allowed) and independent_checks()))
    if lifecycle.final is not None:
        atomic(Path(capture)/'observed-final.txt', redact(lifecycle.final), exclusive=True)
    write_json(Path(capture)/'execution-evidence.json', receipt, exclusive=True)


def repair_turn(engine, task, backend, binding, workspace, capture, action, receipt, independent_checks, **budgets):
    """Parent-harness integration entry point; caller retains its existing fences,
    attempt persistence and failure hold. No runtime lookup, retry or state repair.
    """
    before = tree(workspace)
    prompt = engine.role_prompt(task) + '\nBounded repair: ' + action['text']
    atomic(Path(capture)/'prompt.md', redact(prompt), exclusive=True)
    receipt.update(status='DISPATCH_UNCERTAIN')
    def observe(lifecycle):
        retain_execution(receipt, lifecycle, binding, capture, workspace, before,
                         action['allowed_paths'], independent_checks)
    try:
        final = backend.dispatch(binding, [dict(type='text', text=prompt, text_elements=[])],
            validate_output=lambda _: True, independent_checks=independent_checks,
            observe_execution=observe, **budgets)
        try:
            response = json.loads(final)
            engine.ack(task, response)
        except (ValueError, TypeError, KeyError):
            receipt['validation_failed'] = True
            raise
        if not receipt.get('effects_accounted'):
            raise Rejected('Repair effects remain unresolved')
        receipt.update(status='COMPLETED', response=response)
        return response
    except BaseException as ex:
        receipt.update(status=validation_failure(receipt), failure=str(ex))
        raise
