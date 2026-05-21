from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, List

from holo_cortex_zero.core.logger import logger


@dataclass(frozen=True)
class RequirementIssue:
    name: str
    detail: str
    install_hint: str
    impact: str


class SystemRequirementError(RuntimeError):
    """Raised when required runtime system dependencies are unavailable."""


def _check_executable(name: str, *, install_hint: str, impact: str) -> RequirementIssue | None:
    path = shutil.which(name)
    if not path:
        return RequirementIssue(
            name=name,
            detail=f"`{name}` executable not found in PATH",
            install_hint=install_hint,
            impact=impact,
        )
    try:
        subprocess.run([path, "-version"], check=True, capture_output=True, timeout=5)
    except Exception as exc:
        return RequirementIssue(
            name=name,
            detail=f"`{path} -version` failed: {type(exc).__name__}: {exc}",
            install_hint=install_hint,
            impact=impact,
        )
    return None


def _check_python_magic() -> RequirementIssue | None:
    try:
        import magic

        magic.from_buffer(b"hcz system requirement check", mime=True)
    except Exception as exc:
        return RequirementIssue(
            name="libmagic",
            detail=f"python-magic is not usable: {type(exc).__name__}: {exc}",
            install_hint="Debian/Ubuntu: apt-get install -y libmagic-dev",
            impact="file MIME detection, uploads, message media handling",
        )
    return None


def _check_matrix_e2ee() -> RequirementIssue | None:
    try:
        import nio  # noqa: F401
        import olm  # noqa: F401
        from nio.crypto.attachments import decrypt_attachment  # noqa: F401
    except Exception as exc:
        return RequirementIssue(
            name="libolm / matrix-nio[e2e]",
            detail=f"Matrix E2EE dependencies are not usable: {type(exc).__name__}: {exc}",
            install_hint="Debian/Ubuntu: apt-get install -y libolm-dev",
            impact="Matrix adapter E2EE support",
        )
    return None


def _required_checks() -> List[Callable[[], RequirementIssue | None]]:
    return [
        lambda: _check_executable(
            "ffmpeg",
            install_hint="Debian/Ubuntu: apt-get install -y ffmpeg",
            impact="audio/video conversion, TTS voice conversion, multimodal media handling",
        ),
        lambda: _check_executable(
            "ffprobe",
            install_hint="Debian/Ubuntu: apt-get install -y ffmpeg",
            impact="audio/video duration probing and media preparation",
        ),
        _check_python_magic,
        _check_matrix_e2ee,
    ]


def check_required_system_dependencies() -> None:
    """Fail fast when required non-Python runtime dependencies are unavailable."""

    issues = [issue for check in _required_checks() if (issue := check()) is not None]
    if not issues:
        logger.info("System dependency check passed")
        return

    logger.error("System dependency check failed: missing/unusable runtime dependencies")
    for issue in issues:
        logger.error(
            "System dependency missing: {} | detail={} | impact={} | install_hint={}",
            issue.name,
            issue.detail,
            issue.impact,
            issue.install_hint,
        )
    raise SystemRequirementError(
        "Missing required system dependencies: " + ", ".join(issue.name for issue in issues)
    )
