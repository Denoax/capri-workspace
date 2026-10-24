"""Bounded public phase timings; no payloads, arguments or exception bodies."""
import json
import os
from pathlib import Path
import time
import uuid

from .util import Rejected, now


class CompactionTiming:
    PHASES = {'BEGIN','RPC_SEND_INTENT','RPC_SENT','RPC_ACKNOWLEDGED','LIFECYCLE_RETURNED',
              'FAILED','CLEANUP_BEGIN','CLEANUP_END','LATE_AFTER_FAILURE'}

    def __init__(self, root, role, generation, thread, limit, *, clock=time.monotonic):
        self.path = Path(root)/('compaction-timing-'+str(uuid.uuid4())+'.jsonl')
        self.base = dict(schema=1, role=role, generation=generation, thread=thread, limit_seconds=limit)
        self.clock, self.start = clock, clock()
        self.count, self.bytes, self.failed = 0, 0, False
        self.mark('BEGIN')

    def mark(self, phase, *, rpc_id=None, error_class=None):
        if phase not in self.PHASES or (rpc_id is not None and type(rpc_id) is not int):
            raise Rejected('Invalid compaction timing metadata')
        if self.failed and phase == 'LIFECYCLE_RETURNED':
            phase = 'LATE_AFTER_FAILURE'
        self.failed |= phase == 'FAILED'
        row = dict(self.base, phase=phase, elapsed_seconds=self.clock()-self.start, wall_time=now())
        if rpc_id is not None:row['rpc_id'] = rpc_id
        if error_class is not None:
            if not error_class.isidentifier() or len(error_class)>64:raise Rejected('Invalid error-class metadata')
            row['error_class'] = error_class
        raw = (json.dumps(row, sort_keys=True)+'\n').encode()
        if self.count>=32 or self.bytes+len(raw)>16384:raise Rejected('Compaction timing quota exceeded')
        # The backend serializes these phase markers on its dispatch thread.
        fd = os.open(self.path, os.O_WRONLY|os.O_CREAT|os.O_APPEND|(os.O_EXCL if self.count==0 else 0), 0o600)
        try:
            with os.fdopen(fd,'ab') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
        except BaseException:
            self.failed=True
            raise
        self.count+=1;self.bytes+=len(raw)
