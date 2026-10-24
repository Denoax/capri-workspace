"""Authority lives here, never in text, model JSON, memories or animation cues."""
import asyncio
from dataclasses import dataclass
import hashlib
import json
import secrets
import time


class Denied(ValueError):
    pass


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Denied("Invalid schema or unknown properties")


@dataclass(frozen=True)
class Grant:
    task: str
    epoch: str
    kind: str
    arguments: str
    deadline: float
    policy: str = "capri-policy-v1"


class Broker:
    def __init__(self, store, adapters):
        self.store = store
        self.adapters = adapters
        self.epoch = secrets.token_hex(24)
        self.grants = {}
        self.trusted_ui = False
        self.locked = True
        self.pending = set()

    def revoke(self):
        self.epoch = secrets.token_hex(24)
        for grant in self.grants.values():
            self.store.journal(grant.task, grant.epoch, grant.kind, "CANCELLED")
        self.grants.clear()
        for task in tuple(self.pending):
            task.cancel()
        self.adapters.stop()

    def connect_ui(self):
        self.revoke()
        self.trusted_ui = True

    def disconnect_ui(self):
        self.trusted_ui = False
        self.revoke()

    def set_locked(self, locked):
        if locked != self.locked:
            self.locked = locked
            self.revoke()

    def authorize(self, kind, args, *, origin):
        if origin != "owner-ui" or not self.trusted_ui or self.locked:
            raise Denied("No current unlocked owner input")
        self.adapters.validate(kind, args)
        canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
        task = secrets.token_hex(16)
        grant = Grant(task, self.epoch, kind, canonical, time.monotonic() + 60)
        self.grants[task] = grant
        self.store.journal(task, self.epoch, kind, "AUTHORIZED")
        return grant

    async def execute(self, proposal):
        exact_keys(proposal, ("task", "epoch", "kind", "args", "action_id"))
        if not all(isinstance(proposal[k], str) for k in ("task", "epoch", "kind", "action_id")) or not isinstance(proposal["args"], dict):
            raise Denied("Invalid proposal field types")
        grant = self.grants.get(proposal["task"])
        if not grant or grant.epoch != self.epoch or proposal["epoch"] != self.epoch:
            raise Denied("Unknown or revoked task")
        if not self.trusted_ui or self.locked or time.monotonic() > grant.deadline:
            raise Denied("Expired or inactive grant")
        canonical = json.dumps(proposal["args"], sort_keys=True, separators=(",", ":"))
        if proposal["kind"] != grant.kind or canonical != grant.arguments:
            raise Denied("Action differs from exact owner scope")
        expected_id = hashlib.sha256((grant.task + grant.kind + canonical).encode()).hexdigest()
        if proposal["action_id"] != expected_id:
            raise Denied("Invalid action identity")
        if self.store.action(expected_id):
            raise Denied("Action already journaled; inspect prior effect instead of replaying")
        # Consume before awaiting. Duplicate streams cannot race a second side effect.
        del self.grants[grant.task]
        self.store.journal(expected_id, self.epoch, grant.kind, "RUNNING")
        current = asyncio.current_task()
        self.pending.add(current)
        try:
            result = await self.adapters.run(grant.kind, proposal["args"])
            if grant.epoch != self.epoch:
                self.store.journal(expected_id, grant.epoch, grant.kind, "EFFECT_UNKNOWN", "Revoked while operation was running")
                raise Denied("Revoked; inspect effect journal")
            self.store.journal(expected_id, grant.epoch, grant.kind, "SUCCEEDED", json.dumps(result))
            return result
        except asyncio.CancelledError:
            self.store.journal(expected_id, grant.epoch, grant.kind, "EFFECT_UNKNOWN", "Interrupted; do not replay automatically")
            raise
        except Exception as error:
            self.store.journal(expected_id, grant.epoch, grant.kind, "EFFECT_UNKNOWN", type(error).__name__)
            raise
        finally:
            self.pending.discard(current)

    @staticmethod
    def proposal(grant):
        args = json.loads(grant.arguments)
        key = hashlib.sha256((grant.task + grant.kind + grant.arguments).encode()).hexdigest()
        return {"task": grant.task, "epoch": grant.epoch, "kind": grant.kind, "args": args, "action_id": key}
