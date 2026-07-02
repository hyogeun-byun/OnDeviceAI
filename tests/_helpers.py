from __future__ import annotations

import importlib
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA_WORKER_REQUIREMENTS = {"R-01", "R-02", "R-03", "R-04", "R-26", "R-27"}


def path(rel_path: str) -> Path:
    return ROOT / rel_path


def read(rel_path: str) -> str:
    return path(rel_path).read_text(encoding="utf-8")


def assert_contains(testcase, rel_path: str, *needles: str) -> str:
    text = read(rel_path)
    for needle in needles:
        testcase.assertIn(needle, text, f"{needle!r} not found in {rel_path}")
    return text


def assert_not_contains(testcase, rel_path: str, *needles: str) -> str:
    text = read(rel_path)
    for needle in needles:
        testcase.assertNotIn(needle, text, f"{needle!r} should not remain in {rel_path}")
    return text


def load_path_module(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, path(rel_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_server_module(module_name: str):
    server_root = str(path("src/program_server"))
    if server_root not in sys.path:
        sys.path.insert(0, server_root)
    return importlib.import_module(module_name)


def function_body(source: str, function_name: str) -> str:
    start_marker = f"def {function_name}"
    start = source.index(start_marker)
    next_def = source.find("\n    def ", start + len(start_marker))
    if next_def == -1:
        return source[start:]
    return source[start:next_def]


def write_requirement_log(requirement_id: str, slug: str, *lines: str) -> Path:
    """Write a requirement-named evidence log for later Agent analysis.

    These logs intentionally separate static unittest evidence from field
    evidence that needs real cameras, LAN, browser, or server runtime.
    """
    program_dir = (
        "program_camera_worker"
        if requirement_id in CAMERA_WORKER_REQUIREMENTS
        else "program_server"
    )
    output_dir = path(f"test-results/{program_dir}/requirements")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"{requirement_id}-{slug}.log"
    content = [
        f"requirement_id={requirement_id}",
        f"evidence_slug={slug}",
        f"generated_at={datetime.now(timezone.utc).isoformat()}",
        *lines,
    ]
    log_path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return log_path
