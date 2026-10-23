"""Typed completed-intake holds; never turn a limit error into successful work."""
import json
from .util import NeedsInput, Rejected, redact


class OwnerHold(NeedsInput):
    def __init__(self, outcome, detail, questions=()):
        self.result=dict(outcome=outcome,detail=redact(detail),questions=list(questions),
            model_dispatch='STOPPED',next_action='BOUND_CORE_ANSWER_AND_CHECKED_NEW_ADMISSION' if outcome=='NEEDS_INPUT'
                else 'PARENT_REVIEW_OF_SOURCE_OR_BUDGET_GAP',gate='BLOCKED')
        super().__init__(json.dumps(self.result))


def completed_hold(state, owner, final):
    """Call only after a complete captured lifecycle and zero submitted tasks."""
    if state.db.execute('SELECT id FROM tasks WHERE owner=?',(owner,)).fetchone():return None
    questions=state.questions(owner,blocking=True)
    pending=state.db.execute("SELECT id FROM human_inputs WHERE owner=? AND status='PENDING'",(owner,)).fetchall()
    if questions or pending:
        return OwnerHold('NEEDS_INPUT','The existing core bound-answer/correction route is required.',
            [dict(id=q['id'],task=q['task'],revision=q['revision'],packet_hash=q['packet_hash'],status=q['status']) for q in questions])
    try:value=json.loads(final)
    except (TypeError,ValueError):return None
    if not isinstance(value,dict) or set(value)!={'outcome','detail'}:return None
    if value['outcome']=='NEEDS_INPUT':
        raise Rejected('A question hold needs an actual durable core question, not a model assertion')
    if value['outcome'] not in ('INSUFFICIENT_SOURCE','BUDGET_INFEASIBLE'):return None
    if not isinstance(value['detail'],str) or not 0<len(value['detail'])<=2000:
        raise Rejected('Completed owner hold needs bounded source/budget detail')
    return OwnerHold(value['outcome'],value['detail'])
