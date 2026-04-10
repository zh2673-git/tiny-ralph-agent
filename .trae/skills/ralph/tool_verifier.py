"""Tool verification for Ralph loop."""
import subprocess
import sys
from pathlib import Path
from typing import Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum


class VerificationResult(str, Enum):
    """Verification result enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class VerificationOutput:
    """Output from verification command."""
    result: VerificationResult
    stdout: str
    stderr: str
    return_code: int
    duration_ms: float
    command: str


class ToolVerifier:
    """Verifies task completion by running verification commands."""

    def __init__(self, timeout: int = 60, cwd: Optional[str] = None):
        """
        Initialize tool verifier.

        Args:
            timeout: Maximum time in seconds for verification command
            cwd: Working directory for command execution
        """
        self.timeout = timeout
        self.cwd = cwd or str(Path.cwd())

    def verify(self, command: str) -> VerificationOutput:
        """
        Run verification command and return result.

        Args:
            command: Shell command to execute

        Returns:
            VerificationOutput with result details
        """
        import time

        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd
            )

            duration_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                return VerificationOutput(
                    result=VerificationResult.SUCCESS,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    duration_ms=duration_ms,
                    command=command
                )
            else:
                return VerificationOutput(
                    result=VerificationResult.FAILURE,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    duration_ms=duration_ms,
                    command=command
                )

        except subprocess.TimeoutExpired as e:
            duration_ms = (time.time() - start_time) * 1000
            return VerificationOutput(
                result=VerificationResult.TIMEOUT,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                return_code=-1,
                duration_ms=duration_ms,
                command=command
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return VerificationOutput(
                result=VerificationResult.ERROR,
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration_ms=duration_ms,
                command=command
            )

    def verify_import(self, module_path: str) -> VerificationOutput:
        """
        Verify that a Python module can be imported.

        Args:
            module_path: Python import path (e.g., 'mymodule.submodule')

        Returns:
            VerificationOutput with result
        """
        command = f'{sys.executable} -c "import {module_path}; print(\'OK\')"'
        return self.verify(command)

    def verify_file_exists(self, file_path: str) -> VerificationOutput:
        """
        Verify that a file exists.

        Args:
            file_path: Path to file

        Returns:
            VerificationOutput with result
        """
        path = Path(file_path)
        if path.exists():
            return VerificationOutput(
                result=VerificationResult.SUCCESS,
                stdout=f"File exists: {file_path}",
                stderr="",
                return_code=0,
                duration_ms=0,
                command=f"check file exists: {file_path}"
            )
        else:
            return VerificationOutput(
                result=VerificationResult.FAILURE,
                stdout="",
                stderr=f"File not found: {file_path}",
                return_code=1,
                duration_ms=0,
                command=f"check file exists: {file_path}"
            )

    def verify_python_syntax(self, file_path: str) -> VerificationOutput:
        """
        Verify Python file syntax using py_compile.

        Args:
            file_path: Path to Python file

        Returns:
            VerificationOutput with result
        """
        command = f'{sys.executable} -m py_compile "{file_path}"'
        return self.verify(command)

    def verify_multiple(self, commands: List[str]) -> List[VerificationOutput]:
        """
        Run multiple verification commands.

        Args:
            commands: List of shell commands

        Returns:
            List of VerificationOutput
        """
        return [self.verify(cmd) for cmd in commands]


class CompositeVerifier:
    """Combines multiple verifications into one result."""

    def __init__(self, verifier: ToolVerifier):
        self.verifier = verifier

    def verify_all(self, commands: List[str]) -> Tuple[bool, List[VerificationOutput]]:
        """
        Verify all commands must pass.

        Args:
            commands: List of verification commands

        Returns:
            Tuple of (all_passed, list_of_outputs)
        """
        outputs = self.verifier.verify_multiple(commands)
        all_passed = all(o.result == VerificationResult.SUCCESS for o in outputs)
        return all_passed, outputs

    def verify_any(self, commands: List[str]) -> Tuple[bool, List[VerificationOutput]]:
        """
        Verify at least one command passes.

        Args:
            commands: List of verification commands

        Returns:
            Tuple of (any_passed, list_of_outputs)
        """
        outputs = self.verifier.verify_multiple(commands)
        any_passed = any(o.result == VerificationResult.SUCCESS for o in outputs)
        return any_passed, outputs
