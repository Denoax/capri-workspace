import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('ci_bwrap_profile',Path(__file__).resolve().parents[2]/'tools/ci_bwrap_profile.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class EphemeralRunnerGuardTests(unittest.TestCase):
    def test_loader_layout_must_be_exact_and_existing_alias_cannot_be_replaced(self):
        headers='[Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]'
        target='/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
        self.assertTrue(module.loader_plan(headers,target,None)['created'])
        self.assertFalse(module.loader_plan(headers,target,target)['created'])
        for values in [('unknown',target,None),(headers,'/unknown',None),(headers,target,'/another-loader')]:
            with self.assertRaises(RuntimeError):module.loader_plan(*values)

    def test_daily_host_self_hosted_wrong_repo_and_disabled_global_policy_reject(self):
        environment=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',GITHUB_REPOSITORY='Denoax/capri-workspace',GITHUB_RUN_ID='1')
        release='ID=ubuntu\nVERSION_ID="24.04"\n'
        module.runner_guard(environment,release,'1\n')
        for key,value in [('GITHUB_ACTIONS','false'),('RUNNER_ENVIRONMENT','self-hosted'),('GITHUB_REPOSITORY','elsewhere/repo'),('GITHUB_REPOSITORY','Denoax/capri'),('GITHUB_RUN_ID','')]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                module.runner_guard(dict(environment,**{key:value}),release,'1')
        for os_release,restricted in [(release,'0'),('ID=arch\n','1')]:
            with self.assertRaises(RuntimeError):module.runner_guard(environment,os_release,restricted)


if __name__=='__main__':unittest.main()
