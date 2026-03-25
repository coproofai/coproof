import json
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


RUNNER_SOURCE = textwrap.dedent(
    """
    import contextlib
    import io
    import json
    import traceback
    from pathlib import Path

    def normalize_result(value):
        if isinstance(value, dict):
            sufficient = value.get('sufficient')
            if not isinstance(sufficient, bool):
                raise ValueError("Computation result dict must contain a boolean 'sufficient' field.")
            records = value.get('records')
            if records is not None and not isinstance(records, list):
                raise ValueError("Computation result dict optional 'records' field must be a list.")
            return {
                'evidence': value.get('evidence'),
                'sufficient': sufficient,
                'summary': value.get('summary'),
                'records': records,
            }

        if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[1], bool):
            return {
                'evidence': value[0],
                'sufficient': value[1],
                'summary': None,
            }

        raise ValueError(
            "Computation entrypoint must return {'evidence': ..., 'sufficient': bool} or (evidence, sufficient)."
        )

    def main():
        payload = json.loads(Path('payload.json').read_text(encoding='utf-8'))
        source_code = Path('user_code.py').read_text(encoding='utf-8')
        global_scope = {'__name__': '__main__'}
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                exec(compile(source_code, 'user_code.py', 'exec'), global_scope)
                entrypoint = global_scope.get(payload['entrypoint'])
                if not callable(entrypoint):
                    raise ValueError(f"Entrypoint '{payload['entrypoint']}' is not defined or not callable.")

                value = entrypoint(payload.get('input_data'), payload.get('target'))
                normalized = normalize_result(value)

            response = {
                'completed': True,
                'sufficient': normalized['sufficient'],
                'evidence': normalized['evidence'],
                'summary': normalized.get('summary'),
                'records': normalized.get('records') or [],
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue(),
                'error': None,
            }
        except Exception as error:
            response = {
                'completed': False,
                'sufficient': False,
                'evidence': None,
                'summary': None,
                'records': [],
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue(),
                'error': str(error),
                'traceback': traceback.format_exc(),
            }

        print(json.dumps(response, ensure_ascii=True))

    if __name__ == '__main__':
        main()
    """
)


def run_python_job(payload: dict):
    timeout_seconds = int(payload.get('timeout_seconds') or 120)

    with tempfile.TemporaryDirectory() as temp_dir:
        workdir = Path(temp_dir)
        (workdir / 'user_code.py').write_text(payload['source_code'], encoding='utf-8')
        (workdir / 'payload.json').write_text(json.dumps({
            'entrypoint': payload['entrypoint'],
            'input_data': payload.get('input_data'),
            'target': payload.get('target'),
        }, ensure_ascii=True), encoding='utf-8')
        (workdir / 'runner.py').write_text(RUNNER_SOURCE, encoding='utf-8')

        completed_process = subprocess.run(
            [sys.executable, 'runner.py'],
            capture_output=True,
            text=True,
            cwd=temp_dir,
            timeout=timeout_seconds,
        )

        stdout = completed_process.stdout.strip()
        if not stdout:
            return {
                'completed': False,
                'sufficient': False,
                'evidence': None,
                'summary': None,
                'records': [],
                'stdout': '',
                'stderr': completed_process.stderr.strip(),
                'error': 'Runner produced no structured output.',
                'exit_code': completed_process.returncode,
            }

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return {
                'completed': False,
                'sufficient': False,
                'evidence': None,
                'summary': None,
                'records': [],
                'stdout': stdout,
                'stderr': completed_process.stderr.strip(),
                'error': 'Runner returned malformed JSON output.',
                'exit_code': completed_process.returncode,
            }

        payload['exit_code'] = completed_process.returncode
        if completed_process.stderr.strip():
            payload['stderr'] = ((payload.get('stderr') or '') + completed_process.stderr).strip()
        return payload


def run_computation_job(payload: dict):
    start = time.perf_counter()
    language = (payload.get('language') or 'python').strip().lower()

    if language != 'python':
        return {
            'completed': False,
            'sufficient': False,
            'evidence': None,
            'summary': None,
            'records': [],
            'stdout': '',
            'stderr': '',
            'error': f'Unsupported computation language: {language}',
            'processing_time_seconds': round(time.perf_counter() - start, 6),
        }

    try:
        result = run_python_job(payload)
    except subprocess.TimeoutExpired:
        result = {
            'completed': False,
            'sufficient': False,
            'evidence': None,
            'summary': None,
            'records': [],
            'stdout': '',
            'stderr': '',
            'error': f'Computation timeout after {payload.get("timeout_seconds") or 120} seconds.',
        }

    result['processing_time_seconds'] = round(time.perf_counter() - start, 6)
    return result