"""Select only successful master push CI for the exact prerelease commit."""
import argparse
import json
import re
import subprocess

WORKFLOWS = ('localization.yml', 'cmake.yml', 'msbuild.yml')

def verified_run(payload, commit):
    runs = [r for r in payload['workflow_runs']
            if r['head_sha'] == commit and r['event'] == 'push' and r['head_branch'] == 'master']
    if not runs:
        raise ValueError('No matching master push run')
    run = max(runs, key=lambda r: (r['run_number'], r.get('run_attempt', 1)))
    if run['status'] != 'completed' or run['conclusion'] != 'success':
        raise ValueError('Latest matching workflow has not completed successfully')
    return int(run['id'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        parser.error('A full commit SHA is required')
    for workflow in WORKFLOWS:
        path = f'repos/JWhiteCat/systeminformer/actions/workflows/{workflow}/runs?head_sha={args.commit}&event=push&per_page=100'
        payload = json.loads(subprocess.check_output(['gh', 'api', path], text=True))
        # Fail closed if this unusually busy SHA would require pagination.
        if payload.get('total_count', 0) > len(payload['workflow_runs']):
            raise ValueError('Workflow result truncated; inspect before releasing')
        run_id = verified_run(payload, args.commit)
        if workflow == 'msbuild.yml':
            print(f'BUILD_RUN_ID={run_id}')

if __name__ == '__main__':
    main()
