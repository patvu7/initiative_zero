# ⚠ SECURITY BOUNDARY: This module is in the external zone.

import subprocess
import tempfile
import json
import os

TIMEOUT_SECONDS = 10

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
            env={**os.environ, "PYTHONPATH": tmpdir}
        )

        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                return {"success": True, "output": output, "stderr": result.stderr}
            except json.JSONDecodeError:
                return {"success": True, "output": result.stdout.strip(), "stderr": result.stderr}
        else:
            return {"success": False, "output": result.stdout, "stderr": result.stderr}

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": "Execution timed out"}
    except Exception as e:
        return {"success": False, "output": "", "stderr": str(e)}
    finally:
        # Cleanup
        for f in [module_path, harness_path]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(tmpdir):
            os.rmdir(tmpdir)
