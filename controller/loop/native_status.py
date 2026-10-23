"""Read-only native status: no Store initializer, backend or telemetry refresh."""
import json
from pathlib import Path
from .adapter import process_identity
from .context import persisted_status
from .util import Rejected


def native_status(root,settings,home=None):
    root=Path(root)
    if not root.exists():
        return dict(status='UNINITIALIZED',runtime=str(root),exact_active_occupancy='UNKNOWN',model_dispatch='NOT_STARTED')
    registry=root/'registry.json'
    rows=json.loads(registry.read_text()) if registry.exists() else {}
    if rows and set(rows)!={'thinker','doer','reviewer'}:raise Rejected('Unknown native role registry')
    maintenance=[]
    if home is not None and (root/'supervisor.json').exists():
        from .native_startup import ReadOnlyState
        operation=json.loads((root/'supervisor.json').read_text()).get('maintenance_operation')
        if operation:
            with ReadOnlyState(home) as view:
                for row in view.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_STARTUP' ORDER BY seq"):
                    value=json.loads(row['data'])
                    if value.get('operation')==operation:maintenance.append(dict(seq=row['seq'],milestone=value['milestone'],details=value['details']))
    result={}
    for role,row in rows.items():
        alive=process_identity(row['pid'])==row['process_identity']
        ledgers=[]
        paths=list((root/role).rglob('*context*.json'))
        for path in sorted(paths):
            if path.name not in ('owner-context.json','context-ledger.json'):continue
            status=persisted_status(path)
            match=(status['identity']['thread']==row['thread'] and status['identity']['role_generation']==row['generation'] and status['identity']['server']==str(row['pid'])+':'+str(row['process_identity']) and status['identity']['process']==str(row['process_identity']))
            status.update(path=str(path),matches_registry=match,producer_process_matching=alive)
            if not match or not alive:status['action']={**status['action'],'action':'HOLD','reason':'STALE_PROCESS_OR_REGISTRY_IDENTITY'}
            ledgers.append(status)
        result[role]=dict(registry=row,process_alive_matching=alive,requested_model=settings.model,configured_model=row.get('model'),runtime_reported_model='UNKNOWN',configured_effort=row.get('effort'),context_ledgers=ledgers,exact_active_occupancy='UNKNOWN',completion='NOT_INFERRED_FROM_LIVENESS',next_permitted='INSPECT_IDENTITY_BOUND_ADMISSION' if alive else 'CHECKED_RECOVERY_ONLY')
    return dict(status='OBSERVED_ONLY',runtime=str(root),roles=result,maintenance_operations=maintenance,context_policy=dict(settings.context_policy),native_ui_baseline=12000,effective_profile_window=475000,exact_active_occupancy='UNKNOWN',pending_request='UNKNOWN_WHEN_NOT_BOUND_TO_A_CURRENT_ADMISSION',telemetry_refreshed=False)
