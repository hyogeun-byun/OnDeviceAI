"""Merge per-model LLM benchmark JSONs into a combined comparison report.

benchmark_llm.py 가 모델별로 저장한 model_*.json 파일들을 읽어서
속도 비교표 / 품질 비교표 / 태스크별 응답 예시를 하나의 로그로 출력합니다.

Usage
-----
  # llm_output 폴더의 최신 model_*.json 을 자동으로 찾아 비교:
    python scratch/compare_llm_results.py

  # 비교 대상 폴더 직접 지정:
    python scratch/compare_llm_results.py --input-dir scratch/llm_output

  # 특정 파일만 골라서 비교 (glob 지원):
    python scratch/compare_llm_results.py \\
        --files scratch/llm_output/model_gemma3-2b_*.json \\
                scratch/llm_output/model_qwen2.5-3b_*.json

  # 같은 run-id(타임스탬프)의 모델들만 비교:
    python scratch/compare_llm_results.py --run-id 20260626_120000

  # 결과를 JSON으로도 저장:
    python scratch/compare_llm_results.py --output scratch/compare_result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import shared logic from benchmark_llm (same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from benchmark_llm import format_log, TASKS, _avg_across_tasks  # noqa: E402


BKP_DIR = Path(__file__).parent / "llm_output"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_model_results(paths: list[Path]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Load per-model JSON files saved by benchmark_llm.py.

    Supports both:
      - per-model format  {"model": {...}, "server": ..., ...}
      - combined format   {"models": [...], "server": ..., ...}

    Returns (meta, all_results).
    Duplicate model entries are deduplicated — last file wins.
    """
    all_results: dict[str, dict[str, object]] = {}   # model name → result
    meta: dict[str, object] = {}

    for path in paths:
        try:
            data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  [skip] {path.name}: {exc}", file=sys.stderr)
            continue

        if "model" in data:
            # per-model format
            model_result: dict[str, object] = data["model"]  # type: ignore[assignment]
            name = str(model_result.get("model", path.stem))
            all_results[name] = model_result
            meta = {k: v for k, v in data.items() if k != "model"}
        elif "models" in data:
            # combined format (from --output)
            for r in data["models"]:  # type: ignore[union-attr]
                name = str(r.get("model", "?"))
                all_results[name] = r
            meta = {k: v for k, v in data.items() if k != "models"}

    return meta, list(all_results.values())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge per-model LLM benchmark JSONs into a combined comparison report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=BKP_DIR,
        metavar="DIR",
        help=f"Directory to scan for model_*.json files (default: {BKP_DIR})",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        type=Path,
        default=None,
        metavar="FILE",
        help="Explicit list of per-model JSON files to merge (supports shell glob)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="TIMESTAMP",
        help="Only include files whose name contains this run-id (e.g. 20260626_120000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional path to write the combined JSON result",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available model_*.json files in --input-dir and exit",
    )
    return parser.parse_args()


def main() -> None:
    import datetime

    args = parse_args()

    # --list: just show available files
    if args.list:
        files = sorted(args.input_dir.glob("model_*.json"))
        if not files:
            print(f"No model_*.json files found in {args.input_dir}")
            return
        print(f"\nAvailable model result files in {args.input_dir}:")
        for f in files:
            size_kb = f.stat().st_size // 1024
            print(f"  {f.name}  ({size_kb} KB)")
        print()
        return

    # Collect paths
    if args.files:
        paths = sorted(set(args.files))
    else:
        paths = sorted(args.input_dir.glob("model_*.json"))
        if not paths:
            # Fallback: also try combined JSONs
            paths = sorted(args.input_dir.glob("*.json"))

    # Filter by run-id if given
    if args.run_id:
        paths = [p for p in paths if args.run_id in p.name]

    if not paths:
        print(
            f"No JSON files found.\n"
            f"  input-dir : {args.input_dir}\n"
            f"  run-id    : {args.run_id or '(any)'}\n"
            f"Run 'python scratch/compare_llm_results.py --list' to see available files.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nLoading {len(paths)} file(s):", file=sys.stderr)
    for p in paths:
        print(f"  {p.name}", file=sys.stderr)

    meta, all_results = load_model_results(paths)

    if not all_results:
        print("No model results found in the provided files.", file=sys.stderr)
        sys.exit(1)

    server = str(meta.get("server", "unknown"))
    warmup_runs = int(meta.get("warmup_runs", 0))  # type: ignore[arg-type]
    runs = int(meta.get("runs", 0))  # type: ignore[arg-type]

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BKP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"compare_{timestamp}.log"

    content = format_log(
        all_results=all_results,
        server=server,
        warmup_runs=warmup_runs,
        runs=runs,
        log_path=str(log_path),
    )
    log_path.write_text(content, encoding="utf-8")

    print(f"\nCompare log saved to: {log_path}", file=sys.stderr)
    print(content)

    if args.output:
        combined: dict[str, object] = {
            **meta,
            "compare_timestamp": timestamp,
            "models": all_results,
            "log_path": str(log_path),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(combined, ensure_ascii=False, indent=2))
        print(f"Combined JSON saved to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
