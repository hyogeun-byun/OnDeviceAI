#!/usr/bin/env bash
# run_llm_benchmark.sh
#
# 모델을 하나씩 pull → bench → rm 하여 저장공간을 아끼면서 LLM 벤치마크를 수행합니다.
# 완료 후 compare_llm_results.py 로 전체 비교 로그를 생성합니다.
#
# 사용법:
#   bash scratch/run_llm_benchmark.sh               # 기본 모델 목록으로 실행
#   bash scratch/run_llm_benchmark.sh --runs 3      # 모델당 3회 측정
#   bash scratch/run_llm_benchmark.sh --keep        # 벤치마크 후 모델 보존 (삭제 안 함)
#   bash scratch/run_llm_benchmark.sh --cleanup     # 기존 설치 모델도 정리 후 실행
#
# 옵션:
#   --runs N        측정 횟수 (기본: 5)
#   --warmup N      웜업 횟수 (기본: 2)
#   --models "..."  공백 구분 모델 목록 (기본: MODELS 배열)
#   --keep          벤치마크 후 모델 삭제 안 함
#   --cleanup       실행 전에 현재 설치된 모든 Ollama 모델 삭제
#   --no-compare    마지막 비교 단계 건너뜀
# ---------------------------------------------------------------------------

set -euo pipefail

# ── 기본 설정 ──────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BENCHMARK_PY="$SCRIPT_DIR/benchmark_llm.py"
COMPARE_PY="$SCRIPT_DIR/compare_llm_results.py"
OUTPUT_DIR="$SCRIPT_DIR/llm_output"

RUNS=5
WARMUP=2
KEEP=false
CLEANUP=false
NO_COMPARE=false

# 비교 대상 모델 (exaone3.5:2.4b 와 비슷한 2~3B 크기)
MODELS=(
    "gemma:2b"
    "llama3.2:3b"
    "qwen2.5:3b"
    "exaone3.5:2.4b"
)

# ── 인수 파싱 ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --runs)     RUNS="$2";    shift 2 ;;
        --warmup)   WARMUP="$2";  shift 2 ;;
        --models)   IFS=' ' read -ra MODELS <<< "$2"; shift 2 ;;
        --keep)     KEEP=true;    shift   ;;
        --cleanup)  CLEANUP=true; shift   ;;
        --no-compare) NO_COMPARE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
info() { echo ""; echo "──────────────────────────────────────────────────────"; echo "  $*"; echo "──────────────────────────────────────────────────────"; }
disk_free() { df -h / | awk 'NR==2{print $4 " free (" $5 " used)"}'; }

ollama_installed_models() {
    curl -s http://127.0.0.1:11434/api/tags 2>/dev/null \
        | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null \
        || true
}

ollama_pull() {
    local model="$1"
    log "Pulling $model ..."
    ollama pull "$model"
}

ollama_remove() {
    local model="$1"
    if ollama list 2>/dev/null | grep -q "^${model%:*}"; then
        log "Removing $model to free disk space ..."
        ollama rm "$model" && log "  ✓ removed $model" || log "  ! could not remove $model (skipping)"
    fi
}

# ── 사전 확인 ──────────────────────────────────────────────────────────────
info "LLM Benchmark Runner"
log "Project : $PROJECT_DIR"
log "Models  : ${MODELS[*]}"
log "Runs    : $RUNS  Warmup: $WARMUP"
log "Keep    : $KEEP"
log "Cleanup : $CLEANUP"
log "Disk    : $(disk_free)"
echo ""

# Ollama 서버 확인
if ! curl -sf http://127.0.0.1:11434/ >/dev/null 2>&1; then
    log "ERROR: Ollama server is not running at http://127.0.0.1:11434"
    log "       Start it with:  ollama serve"
    exit 1
fi
log "✓ Ollama server reachable"

# ── 기존 모델 정리 (--cleanup) ──────────────────────────────────────────────
if [[ "$CLEANUP" == "true" ]]; then
    info "Cleaning up all installed Ollama models"
    installed=$(ollama_installed_models)
    if [[ -z "$installed" ]]; then
        log "No models currently installed."
    else
        while IFS= read -r m; do
            [[ -z "$m" ]] && continue
            log "Removing existing model: $m"
            ollama rm "$m" && log "  ✓ removed" || log "  ! failed (skipping)"
        done <<< "$installed"
    fi
    log "Disk after cleanup: $(disk_free)"
fi

# ── 공유 Run ID 생성 (모든 모델 결과를 같은 폴더에 묶음) ───────────────────
RUN_ID="$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$OUTPUT_DIR"
log "Run ID  : $RUN_ID"
log "Output  : $OUTPUT_DIR"

# 성공/실패 추적
SUCCESS_MODELS=()
FAILED_MODELS=()

# ── 모델별 pull → bench → rm ────────────────────────────────────────────────
for MODEL in "${MODELS[@]}"; do
    info "Model: $MODEL"
    log "Disk before pull : $(disk_free)"

    # Pull
    if ! ollama_pull "$MODEL"; then
        log "ERROR: Failed to pull $MODEL — skipping"
        FAILED_MODELS+=("$MODEL")
        continue
    fi
    log "Disk after pull  : $(disk_free)"

    # Benchmark (단일 모델, 공유 run-id 사용)
    log "Running benchmark for $MODEL ..."
    if python3 "$BENCHMARK_PY" \
        --models "$MODEL" \
        --runs "$RUNS" \
        --warmup-runs "$WARMUP" \
        --run-id "$RUN_ID" \
        2>&1; then
        log "✓ Benchmark complete for $MODEL"
        SUCCESS_MODELS+=("$MODEL")
    else
        log "! Benchmark failed for $MODEL"
        FAILED_MODELS+=("$MODEL")
    fi

    # Remove (--keep 옵션이 없으면 삭제)
    if [[ "$KEEP" == "false" ]]; then
        ollama_remove "$MODEL"
        log "Disk after remove: $(disk_free)"
    else
        log "(--keep: model retained)"
    fi
done

# ── 비교 리포트 생성 ────────────────────────────────────────────────────────
echo ""
info "Benchmark Summary"
log "Succeeded : ${SUCCESS_MODELS[*]:-none}"
log "Failed    : ${FAILED_MODELS[*]:-none}"

if [[ "$NO_COMPARE" == "false" && ${#SUCCESS_MODELS[@]} -ge 1 ]]; then
    log "Generating combined comparison report (run-id: $RUN_ID) ..."
    python3 "$COMPARE_PY" \
        --input-dir "$OUTPUT_DIR" \
        --run-id "$RUN_ID" \
        --output "$OUTPUT_DIR/compare_${RUN_ID}.json" \
        2>&1 \
    && log "✓ Combined report saved to $OUTPUT_DIR/compare_${RUN_ID}.log" \
    || log "! compare_llm_results.py failed"
elif [[ ${#SUCCESS_MODELS[@]} -lt 1 ]]; then
    log "No successful benchmarks — skipping compare step."
fi

echo ""
log "Final disk : $(disk_free)"
log "All output : $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*"$RUN_ID"* 2>/dev/null || true
