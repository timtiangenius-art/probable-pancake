"""Work out a public URL prefix for the author's pictures.

HyperFrames renders in the cloud, so it can only fetch pictures over HTTPS — a
path on this machine is invisible to it. The pictures therefore have to live
somewhere public first. When the plot lives in a public GitHub repository, the
repository itself is that host, and this module derives the raw URL prefix.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

RAW_HOST = "https://raw.githubusercontent.com"
GITHUB_REMOTE_RE = re.compile(
    r"""(?:git@github\.com:|https?://(?:[^@/]+@)?github\.com/)
        (?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?/?$""",
    re.VERBOSE,
)


class HostingError(RuntimeError):
    """Raised when a public URL prefix cannot be derived."""


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HostingError(f"git {' '.join(args)} failed: {exc}") from exc
    return result.stdout.strip()


def parse_github_remote(remote_url: str) -> tuple[str, str]:
    """Return ``(owner, repo)`` for a GitHub remote URL."""
    match = GITHUB_REMOTE_RE.match(remote_url.strip())
    if not match:
        raise HostingError(f"not a GitHub remote: {remote_url!r}")
    return match.group("owner"), match.group("repo")


def github_raw_base(plot_dir: Path) -> str:
    """Build the ``raw.githubusercontent.com`` prefix for files in ``plot_dir``.

    Picture paths are relative to the plot file, so the prefix has to include
    the plot's own directory within the repository.
    """
    plot_dir = Path(plot_dir).resolve()
    root = Path(_git(["rev-parse", "--show-toplevel"], plot_dir))
    owner, repo = parse_github_remote(_git(["remote", "get-url", "origin"], plot_dir))
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], plot_dir)
    if branch == "HEAD":
        raise HostingError("detached HEAD — check out a branch before hosting pictures")

    relative = plot_dir.relative_to(root).as_posix()
    suffix = f"/{relative}" if relative != "." else ""
    return f"{RAW_HOST}/{owner}/{repo}/{branch}{suffix}"


def resolve_asset_base(asset_base: str, plot_dir: Path) -> str:
    """Expand the ``github`` shorthand; pass any other prefix through."""
    if asset_base.strip().lower() == "github":
        return github_raw_base(plot_dir)
    return asset_base
