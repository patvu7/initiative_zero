# ⚠ SECURITY BOUNDARY: This module is in the external zone.

import subprocess
import tempfile
import json
import os
import shutil

TIMEOUT_SECONDS = 10
# TODO(prod): Run in container sandbox (gVisor/Firecracker), not just subprocess
# TODO(prod): Memory limit enforcement (current: unbounded)

def execute_python(code: str, test_harness: str) -> dict:
    """Execute generated Python code with a test harness in a subprocess sandbox.

    Args:
        code: The generated Python module code
        test_harness: Python code that imports the module, runs a test case,
                      and prints JSON result to stdout

    Returns:
        {"success": bool, "output": dict or str, "stderr": str}
    """
    tmpdir = tempfile.mkdtemp(prefix="iz_exec_")
    module_path = os.path.join(tmpdir, "generated_module.py")
    harness_path = os.path.join(tmpdir, "test_harness.py")

    try:
        # Write the generated module
        with open(module_path, 'w') as f:
            f.write(code)

        # Write the test harness
        with open(harness_path, 'w') as f:
            f.write(f"import sys\nsys.path.insert(0, '{tmpdir}')\n")
            f.write(test_harness)

        # Execute in subprocess with timeout
        result = subprocess.run(
            ['python3', harness_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=tmpdir,
            env={**os.environ, "PYTHONPATH": tmpdir, "PYTHONDONTWRITEBYTECODE": "1"}
        )

        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                return {"success": True, "output": output, "stderr": result.stderr}
            except json.JSONDecodeError:
                return {"success": True, "output": result.stdout.strip(), "stderr": result.stderr}
        else:
            stderr_lines = result.stderr.strip().split('\n')
            last_error = stderr_lines[-1] if stderr_lines else "Unknown error"
            return {"success": False, "output": result.stdout, "stderr": result.stderr, "error_summary": last_error}

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": "Execution timed out"}
    except Exception as e:
        return {"success": False, "output": "", "stderr": str(e)}
    finally:
        # Cleanup — use shutil.rmtree to remove tmpdir and any subdirectories
        # (e.g. __pycache__ created by Python import)
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
