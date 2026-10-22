"""Portable explicit native settings. No credential discovery or model fallback."""
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import sysconfig
from types import MappingProxyType
from .util import Rejected

ROLES = ('thinker', 'doer', 'reviewer')
MODEL = 'gpt-6.1-sol'


@dataclass(frozen=True)
class Settings:
    binary: str
    auth_file: str
    state_dir: str
    model: str = MODEL
    efforts: dict = field(default_factory=lambda: dict(thinker='medium', doer='medium', reviewer='high'))
    binary_sha256: str = '399ff69c431c066e40de318fba45c2b07f45a76b19939d247ee4828fc70c4215'

    def __post_init__(self):
        if self.model != MODEL or set(self.efforts) != set(ROLES):
            raise Rejected('Exact Sol model and three effort settings required')
        if any(e not in ('medium', 'high') for e in self.efforts.values()):
            raise Rejected('Effort not supported by supplied model profile')
        if not all(isinstance(x, str) and x for x in (self.binary, self.auth_file, self.state_dir)):
            raise Rejected('Explicit executable, existing auth mount and private state directory required')
        object.__setattr__(self, 'efforts', MappingProxyType(dict(self.efforts)))

    def executable(self):
        value = shutil.which(self.binary)
        if not value:
            raise Rejected('Configured Codex executable unavailable')
        return str(Path(value).resolve())

    def config(self, role, phase='read', mcp=None, hosted_research=False):
        from .confinement import config
        if role not in ROLES or phase not in ('read', 'write') or (phase == 'write' and role != 'doer'):
            raise Rejected('Invalid native role/phase')
        mount_role = 'doer' if phase == 'write' else role if role != 'doer' else 'preflight'
        text = config(mount_role, mcp)
        if hosted_research:
            if role != 'thinker':
                raise Rejected('Hosted research is confined to Thinker')
            text = text.replace('web_search = "disabled"', 'web_search = "live"')
        # Clone every explicit filesystem deny into the named recovery profile.
        # No generic sandboxPolicy override: it could discard private-path rules.
        permission_block = text[text.index('[permissions.role]'):text.index('[shell_environment_policy]')]
        recovery = permission_block.replace('[permissions.role]', '[permissions.recovery]').replace(
            '[permissions.role.filesystem]', '[permissions.recovery.filesystem]').replace(
            'extends = ":workspace"', 'extends = ":read-only"')
        text += '\n' + recovery
        if phase == 'write':
            text = text.replace('default_permissions = "role"', 'default_permissions = "recovery"')
        baseline = 'high' if mount_role == 'reviewer' else 'medium'
        return text.replace('model_reasoning_effort = "' + baseline + '"',
                            'model_reasoning_effort = "' + self.efforts[role] + '"')


def policy_path(config=None):
    """Resolve explicit policy or the shipped policy; never install a personal skill."""
    config = config or {}
    path = Path(config['reference_policy']).expanduser().resolve() if config.get('reference_policy') else Path(__file__).resolve().parents[1]/'policies/reference-led-design.md'
    if not path.is_file() and not config.get('reference_policy'):
        path = Path(sysconfig.get_path('data'))/'share/codex-three-role-workflow/reference-led-design.md'
    if not path.is_file():
        raise Rejected('Configured/shipped reference policy unavailable')
    return path
