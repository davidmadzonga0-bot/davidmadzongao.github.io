from __future__ import annotations

from pathlib import Path


def project_env_path() -> Path:
    return Path.cwd() / ".env"


def upsert_env_values(path: Path, updates: dict[str, str]) -> None:
    """Create or update KEY=VALUE lines in a .env file without touching other keys."""
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    remaining = dict(updates)
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue

        key, _, _ = line.partition("=")
        key = key.strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}")
        else:
            new_lines.append(line)

    if remaining:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key, value in remaining.items():
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
