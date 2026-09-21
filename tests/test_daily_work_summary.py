from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from agents.daily_work_summary import RepositoryConfig, build_summary_evidence, day_window
from agents.concept_relevance import daily_work_has_no_changes as concept_no_changes
from orchestrator.run_daily import daily_work_has_no_changes as orchestrator_no_changes


class CommitOnlySummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'tracked.txt').write_text('baseline\n')
        self.commit('baseline', '2026-09-17T12:00:00+08:00')

    def git(self, *args, date=None):
        env = os.environ.copy()
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        return subprocess.run(['git', '-C', str(self.repo), *args], env=env,
                              check=True, text=True, capture_output=True).stdout

    def commit(self, message, date='2026-09-20T12:00:00+08:00'):
        self.git('add', '.')
        self.git('commit', '-m', message, date=date)

    def evidence(self, name='sample'):
        start, end = day_window('2026-09-21', ZoneInfo('Asia/Shanghai'))
        return build_summary_evidence(RepositoryConfig(name, self.repo), '2026-09-21', start, end, {})

    def test_dirty_primary_and_linked_worktree_do_not_trigger_generation(self):
        (self.repo / 'tracked.txt').write_text('staged\n')
        self.git('add', 'tracked.txt')
        (self.repo / 'tracked.txt').write_text('unstaged\n')
        (self.repo / 'untracked_secret.py').write_text('new file\n')
        wt = Path(self.tmp.name) / 'worktree'
        self.git('worktree', 'add', '-b', 'other', str(wt))
        (wt / 'worktree_secret.py').write_text('new file\n')
        result = self.evidence()
        self.assertEqual('no_change', result.evidence_type)
        self.assertFalse(result.should_call_llm)
        for filename in ['tracked.txt', 'untracked_secret.py', 'worktree_secret.py']:
            self.assertNotIn(filename, result.markdown)
        state = {'agents': {'daily_work_summary': {'status': 'success', 'repositories': [
            {'evidence_type': result.evidence_type}]}}}
        self.assertTrue(concept_no_changes(state))
        self.assertTrue(orchestrator_no_changes(state))

    def test_committed_files_only_are_included(self):
        (self.repo / 'committed.py').write_text('print(1)\n')
        self.commit('Add committed feature')
        (self.repo / 'uncommitted_secret.py').write_text('print(2)\n')
        result = self.evidence()
        self.assertEqual('confirmed_change', result.evidence_type)
        self.assertTrue(result.should_call_llm)
        self.assertIn('committed.py', result.markdown)
        self.assertIn('Add committed feature', result.markdown)
        self.assertNotIn('uncommitted_secret.py', result.markdown)

    def test_commit_on_other_branch_is_included(self):
        self.git('checkout', '-b', 'feature')
        (self.repo / 'feature.py').write_text('feature\n')
        self.commit('Other branch commit')
        self.git('checkout', 'main')
        result = self.evidence()
        self.assertEqual('confirmed_change', result.evidence_type)
        self.assertIn('Other branch commit', result.markdown)

    def test_automatic_publish_commit_remains_excluded(self):
        (self.repo / 'daily_report').mkdir()
        (self.repo / 'daily_report' / 'manifest.json').write_text('{}')
        self.commit('Publish daily learning report 2026-09-20')
        result = self.evidence('DailyLearningAssistant')
        self.assertEqual('no_change', result.evidence_type)
        self.assertFalse(result.should_call_llm)
        self.assertIn('已忽略自身自动发布日报产生的 1 个提交', result.markdown)

    def test_missing_repository_is_not_no_change(self):
        start, end = day_window('2026-09-21', ZoneInfo('Asia/Shanghai'))
        result = build_summary_evidence(RepositoryConfig('missing', self.repo / 'missing'),
                                        '2026-09-21', start, end, {})
        self.assertEqual('unavailable', result.evidence_type)


if __name__ == '__main__':
    unittest.main()
