from pathlib import Path
import importlib.util
import unittest

path = Path(__file__).resolve().parents[1] / 'tools/release/verify_ci.py'
spec = importlib.util.spec_from_file_location('verify_ci', path)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
SHA = 'a' * 40

def run(**kwargs):
    data = dict(id=1, head_sha=SHA, event='push', head_branch='master', run_number=1,
                status='completed', conclusion='success')
    data.update(kwargs)
    return data

class ReleaseCiTests(unittest.TestCase):
    def test_exact_master_push(self):
        self.assertEqual(ci.verified_run({'workflow_runs': [run()]}, SHA), 1)
    def test_fail_closed_on_other_sha_or_event_or_branch(self):
        for record in (run(head_sha='b'*40), run(event='pull_request'), run(head_branch='other')):
            with self.assertRaises(ValueError): ci.verified_run({'workflow_runs': [record]}, SHA)
    def test_latest_run_must_succeed_not_previous(self):
        with self.assertRaises(ValueError):
            ci.verified_run({'workflow_runs': [run(), run(id=2, run_number=2, conclusion='failure')]}, SHA)
    def test_running_or_cancelled_is_not_success(self):
        for record in (run(status='in_progress'), run(conclusion='cancelled')):
            with self.assertRaises(ValueError): ci.verified_run({'workflow_runs': [record]}, SHA)
    def test_workflow_only_deliberate_tags_and_checks_reuploaded_assets(self):
        source=(path.parents[2]/'.github/workflows/bilingual-prerelease.yml').read_text()
        self.assertIn("tags: ['bilingual-v*-preview.*']", source)
        self.assertIn("github.repository == 'JWhiteCat/systeminformer'", source)
        self.assertIn('--verify-tag --draft --prerelease --latest=false', source)
        self.assertLess(source.index('--destination remote-verification'), source.index('--draft=false'))
        self.assertNotIn('--clobber', source)

    def test_manual_publication_is_pinned_and_non_overwriting(self):
        source=(path.parents[2]/'.github/workflows/bilingual-prerelease.yml').read_text()
        self.assertIn('workflow_dispatch:', source)
        self.assertIn("github.ref == 'refs/heads/master'", source)
        self.assertIn('EXPECTED_SHA: ${{ github.sha }}', source)
        self.assertIn('git/matching-refs/tags/$RELEASE_TAG', source)
        self.assertIn('repos/$GH_REPO/commits/master', source)
        self.assertIn('-f "ref=refs/tags/$RELEASE_TAG" -f "sha=$EXPECTED_SHA"', source)
        self.assertLess(source.index('--destination release-assets --commit'), source.index('gh api --method POST'))
        self.assertLess(source.index('gh api --method POST'), source.index('gh release create'))
        self.assertNotIn('--method PATCH', source)

if __name__ == '__main__': unittest.main()
