"""TD-236 — `record_request_analysis` runs from a git WORKTREE and stamps the worktree's commit.

Every sprint is worked in a worktree, and a worktree has no `.env` (the credential lives only in
the main checkout). The command used to read `.env` from its own tree only, so it had to be run
from the main checkout — which then stamped the MAIN checkout's HEAD on an analysis of another
branch. Now the credential is found through git's common dir, and the SHA is still read from the
tree the command runs in.

⚠ `git` is FAKED here, at the `subprocess.run` seam: the deploy gate's test image
(`python:3.11-slim`) has no git binary, and a test may not skip. The fake answers the two
questions the command asks exactly as git does for a worktree — `rev-parse HEAD` is the CWD's own
commit, and `--git-common-dir` from a worktree is the MAIN checkout's `.git`.
"""
import os
import subprocess
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship.management.commands import record_request_analysis as cmd


class TestFromAWorktree(SimpleTestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.main = os.path.join(base, 'main')
        self.tree = os.path.join(base, 'tree')
        os.makedirs(os.path.join(self.main, '.git'))
        os.makedirs(self.tree)
        with open(os.path.join(self.main, '.env'), 'w', encoding='utf-8') as fh:
            fh.write('HALATUJU_TEST_KEY=from-main\n')
        self.heads = {self.main: 'a' * 40, self.tree: 'b' * 40}
        self.calls = []

    def tearDown(self):
        self._tmp.cleanup()

    def _git(self, args, cwd=None, **_):
        self.calls.append((tuple(args), cwd))
        if args[:3] == ['git', 'rev-parse', 'HEAD']:
            return subprocess.CompletedProcess(args, 0, stdout=self.heads[cwd] + '\n', stderr='')
        if '--git-common-dir' in args:
            return subprocess.CompletedProcess(args, 0, stdout=os.path.join(self.main, '.git') + '\n',
                                               stderr='')
        return subprocess.CompletedProcess(args, 128, stdout='', stderr='fatal')

    def test_a_worktree_reads_the_main_checkouts_env(self):
        with mock.patch.object(cmd.subprocess, 'run', side_effect=self._git):
            self.assertEqual(cmd._env_path(self.tree), os.path.join(self.main, '.env'))
        self.assertEqual(self.calls[0][1], self.tree, 'git is asked FROM the tree being run in')

    def test_the_sha_is_the_worktrees_own_commit_not_mains(self):
        with mock.patch.object(cmd.subprocess, 'run', side_effect=self._git):
            self.assertEqual(cmd._repo_sha(self.tree), 'b' * 40)

    def test_a_tree_with_its_own_env_keeps_it(self):
        own = os.path.join(self.tree, '.env')
        with open(own, 'w', encoding='utf-8') as fh:
            fh.write('HALATUJU_TEST_KEY=own\n')
        with mock.patch.object(cmd.subprocess, 'run', side_effect=self._git):
            self.assertEqual(cmd._env_path(self.tree), own)

    def test_the_main_checkout_reads_its_own(self):
        with mock.patch.object(cmd.subprocess, 'run', side_effect=self._git):
            self.assertEqual(cmd._env_path(self.main), os.path.join(self.main, '.env'))

    def test_no_git_at_all_falls_back_to_the_trees_own_path(self):
        with mock.patch.object(cmd.subprocess, 'run', side_effect=FileNotFoundError('git')):
            self.assertEqual(cmd._env_path(self.tree), os.path.join(self.tree, '.env'))

    def test_a_git_failure_never_reads_a_relative_env(self):
        """A failed `rev-parse` prints nothing; that must not become `.env` relative to the CWD."""
        failing = subprocess.CompletedProcess([], 128, stdout='', stderr='fatal')
        with mock.patch.object(cmd.subprocess, 'run', return_value=failing):
            self.assertEqual(cmd._env_path(self.tree), os.path.join(self.tree, '.env'))

    def test_the_credential_reader_and_writer_both_use_the_resolved_path(self):
        with mock.patch.object(cmd.subprocess, 'run', side_effect=self._git), \
                mock.patch.object(cmd, '_REPO_ROOT', self.tree), \
                mock.patch.dict(os.environ, {'HALATUJU_TEST_KEY': ''}):
            self.assertEqual(cmd._env_value('HALATUJU_TEST_KEY'), 'from-main')
            cmd._env_write({'HALATUJU_TEST_KEY': 'rotated'})
        with open(os.path.join(self.main, '.env'), encoding='utf-8') as fh:
            self.assertIn('HALATUJU_TEST_KEY=rotated', fh.read())
        self.assertFalse(os.path.exists(os.path.join(self.tree, '.env')))
