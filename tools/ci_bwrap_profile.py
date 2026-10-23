#!/usr/bin/env python3
"""Load/remove only the CI bwrap profile on an ephemeral GitHub-hosted runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def runner_guard(environment, os_release, restricted):
    if (environment.get('GITHUB_ACTIONS') != 'true'
            or environment.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or environment.get('GITHUB_REPOSITORY') != 'Denoax/capri'
            or not environment.get('GITHUB_RUN_ID')
            or 'ID=ubuntu' not in os_release.splitlines()
            or 'VERSION_ID="24.04"' not in os_release.splitlines()
            or restricted.strip() != '1'):
        raise RuntimeError('CI policy is restricted to this disposable Ubuntu GitHub-hosted runner; global userns restrictions must remain enabled')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','remove'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    runner_guard(os.environ,Path('/etc/os-release').read_text(),
                 Path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns').read_text())
    profile=Path(__file__).resolve().parents[1]/'examples/ci/bwrap.apparmor'
    fingerprint=hashlib.sha256(profile.read_bytes()).hexdigest()
    receipt=args.output/'ci-apparmor-profile.json'
    if args.action=='remove':
        saved=json.loads(receipt.read_text())
        if saved['profile_sha256']!=fingerprint or saved['run']!=os.environ['GITHUB_RUN_ID']:
            raise RuntimeError('CI profile cleanup identity changed')
    else:
        args.output.mkdir(parents=True,exist_ok=True)
        if receipt.exists():raise RuntimeError('CI profile already has an install receipt')
        status=json.loads(subprocess.check_output(['sudo','-n','aa-status','--json'],text=True))
        if any(name in status['profiles'] for name in ['capri-ci-bwrap','capri-ci-no-caps','bwrap']):
            raise RuntimeError('Existing bwrap policy must not be replaced')
        subprocess.run(['apparmor_parser','--skip-kernel-load','--skip-read-cache',str(profile)],check=True)
    subprocess.run(['sudo','-n','apparmor_parser','--'+('add' if args.action=='install' else 'remove'),
                    '--skip-read-cache',str(profile)],check=True)
    runner_guard(os.environ,Path('/etc/os-release').read_text(),
                 Path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns').read_text())
    result=dict(origin='ACTUAL_EPHEMERAL_CI_POLICY_ACTION',action=args.action,
        profile_sha256=fingerprint,run=os.environ['GITHUB_RUN_ID'],global_userns_restriction='UNCHANGED_ENABLED')
    with (receipt if args.action=='install' else args.output/'ci-apparmor-cleanup.json').open('x') as file:
        json.dump(result,file,indent=2);file.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
