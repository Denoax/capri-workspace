"""Proposed native lineage references; no operator action or launch authority.

This resolves one immutable native preparation artifact back to the exact core
receipt. Legacy inline lineage still uses the original equality checks.
"""
import json
from pathlib import Path

from .util import Rejected, digest

PROJECTED_KEYS = ('parent_task', 'parent_packet_hash', 'revision', 'human_answers',
                  'human_corrections', 'correction', 'prior_candidate',
                  'prior_candidate_files', 'recontract_operation', 'successor_owner')
ORIGIN = 'ACTUAL_COMMITTED_CORE_FOREGROUND_RECONTRACT'


def compact_native_request(request):
    lineage = request.get('lineage', {})
    if not isinstance(lineage, dict) or 'full_core_lineage' not in lineage:
        return request
    if 'lineage_reference' in request:
        raise Rejected('Conflicting native lineage reference')
    return {**{k: v for k, v in request.items() if k != 'lineage'},
            'lineage_reference': {'packet_pointer': '/lineage',
                                 'full_core_lineage': lineage['full_core_lineage']}}


def resolve_native_lineage(home, projected, saved):
    """Return full committed lineage only after exact reference/projection checks."""
    if not isinstance(saved, dict) or not isinstance(projected, dict):
        raise Rejected('Missing committed native lineage')
    full = saved['lineage']
    ref = projected.get('full_core_lineage')
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256', 'origin'} or ref['origin'] != ORIGIN:
        raise Rejected('Malformed native lineage reference')
    expected = Path(home).resolve()/'inputs/native-recontract'/full['recontract_operation']/'prepared.json'
    if ref['path'] != str(expected) or any(p.is_symlink() for p in (expected, *expected.parents)):
        raise Rejected('Native lineage reference path changed')
    try:
        raw = expected.read_bytes()
        if digest(raw) != ref['sha256']:
            raise Rejected('Native lineage reference hash changed')
        artifact = json.loads(raw)
    except (OSError, ValueError) as ex:
        raise Rejected('Native lineage artifact is unavailable or malformed') from ex
    if artifact.get('schema_version') != 1 or artifact.get('route') != 'NATIVE_APP_SERVER_ONLY' or artifact.get('prepared') != saved:
        raise Rejected('Native artifact differs from committed preparation')
    exact = {k: full[k] for k in PROJECTED_KEYS}
    exact['full_core_lineage'] = ref
    if projected != exact:
        raise Rejected('Native lineage projection changed committed fields')
    return full
