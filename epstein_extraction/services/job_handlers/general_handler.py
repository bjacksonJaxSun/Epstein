"""
General purpose job handler - executes PowerShell, Python, shell commands.

This handler supports multiple action types:
- powershell: Execute PowerShell commands
- python: Execute Python scripts
- shell: Execute shell commands (cmd on Windows)
- executable: Run arbitrary executables

Example payloads:
    # PowerShell command
    {"action": "powershell", "command": "Get-Process | Sort CPU -Desc | Select -First 10"}

    # Python script
    {"action": "python", "script": "C:\\scripts\\process_batch.py", "args": ["--input", "data.csv"]}

    # Shell command
    {"action": "shell", "command": "dir /s *.pdf"}

    # Custom executable
    {"action": "executable", "path": "C:\\tools\\ocr.exe", "args": ["-i", "image.png", "-o", "output.txt"]}
"""

import subprocess
import time
import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class JobResult:
    """Result of a job execution."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    result_data: Optional[dict] = None


def handle_general_job(payload: dict) -> JobResult:
    """
    Handle a general job based on action type.

    Args:
        payload: Job payload containing:
            - action: "powershell|python|shell|executable"
            - command: Command string (for powershell/shell)
            - script: Script path (for python)
            - path: Executable path (for executable)
            - args: Optional list of arguments
            - timeout: Optional timeout in seconds (default: 300)
            - working_dir: Optional working directory

    Returns:
        JobResult with success status, output, and any errors
    """
    action = payload.get('action', 'powershell')
    timeout = payload.get('timeout', 300)
    working_dir = payload.get('working_dir')

    start_time = time.time()

    try:
        shell = False
        cmd = None

        if action == 'powershell':
            command = payload.get('command', '')
            if not command:
                return JobResult(success=False, error="No command specified for powershell action")
            cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command]

        elif action == 'python':
            script = payload.get('script', '')
            if not script:
                return JobResult(success=False, error="No script specified for python action")
            args = payload.get('args', [])
            cmd = ['python', script] + args

        elif action == 'shell':
            command = payload.get('command', '')
            if not command:
                return JobResult(success=False, error="No command specified for shell action")
            # On Windows use cmd, on Unix use shell
            if platform.system() == 'Windows':
                cmd = command
                shell = True
            else:
                cmd = ['/bin/sh', '-c', command]

        elif action == 'executable':
            exe_path = payload.get('path', '')
            if not exe_path:
                return JobResult(success=False, error="No path specified for executable action")
            args = payload.get('args', [])
            cmd = [exe_path] + args

        else:
            return JobResult(success=False, error=f"Unknown action: {action}")

        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
            shell=shell
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Combine stdout and stderr for output
        output = result.stdout
        if result.stderr:
            output += "\n--- stderr ---\n" + result.stderr if output else result.stderr

        return JobResult(
            success=result.returncode == 0,
            output=output,
            exit_code=result.returncode,
            error=result.stderr if result.returncode != 0 else None,
            result_data={'duration_ms': duration_ms, 'action': action}
        )

    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start_time) * 1000)
        output = ""
        if e.stdout:
            output = e.stdout if isinstance(e.stdout, str) else e.stdout.decode('utf-8', errors='replace')
        if e.stderr:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode('utf-8', errors='replace')
            output += "\n--- stderr ---\n" + stderr if output else stderr

        return JobResult(
            success=False,
            output=output,
            error=f"Timeout after {timeout} seconds",
            exit_code=-1,
            result_data={'duration_ms': duration_ms, 'action': action, 'timeout': True}
        )

    except FileNotFoundError as e:
        return JobResult(
            success=False,
            error=f"Executable not found: {e}",
            exit_code=-1
        )

    except PermissionError as e:
        return JobResult(
            success=False,
            error=f"Permission denied: {e}",
            exit_code=-1
        )

    except Exception as e:
        return JobResult(
            success=False,
            error=str(e),
            exit_code=-1
        )
