---
marp: true
paginate: true
math: katex
theme: uncover
class: invert
title: 이구동성 텔레파시 — 1차 발표
description: 분산 엣지 디바이스 기반 멀티-휴먼 포즈 동기화 AI 게임
---

<!--
변환 방법:
  npx @marp-team/marp-cli@latest docs/presentation/1st-review.md --pptx -o 1차발표.pptx
  npx @marp-team/marp-cli@latest docs/presentation/1st-review.md --pdf  -o 1차발표.pdf
  npx @marp-team/marp-cli@latest docs/presentation/1st-review.md --html -o 1차발표.html   # reveal형 단일 HTML
미리보기: VS Code "Marp for VS Code" 확장 설치 후 우상단 미리보기.
실측 수치는 라즈베리파이 CPU(XNNPACK)·MoveNet int8 192×192 기준. 환경이 다르면 재측정.
-->

# 이구동성 텔레파시
### *Telepathy Sync*
분산 엣지 디바이스 기반 **멀티-휴먼 포즈 동기화 AI 게임**

SW Bootcamp 13기 · A반 3팀
발표일 2026.◻.◻

> "여러 대의 라즈베리파이가 각자 사람을 보고,
> 클라우드 없이 서로의 '자세 일치도'를 실시간으로 합의한다."

---

## 주제 및 결과 요약

- **문제 정의** — 서로를 볼 수 없는 N명이 제시어만 보고 같은 동작을 취한다.
  *카메라마다 위치·거리·화각이 다른* 상태에서 "얼마나 똑같은 자세인가"를 강건하게 정량화하는 것이 핵심 난제.
- **접근** — 픽셀·좌표가 아닌 **관절 각도 공간**에서 비교 → 카메라 외부 파라미터에 불변(invariant). 추론·LLM·TTS를 **전부 엣지에서** 수행.
- **결과** — 카메라 워커 N대(MoveNet **int8**) ↔ FastAPI 서버(10Hz 결정론 상태머신) ↔ 브라우저 2종을 잇는 **엔드투엔드 실시간 시스템 완성**. 클라우드 의존 0.

`COCO 17 keypoint · 8-관절 각도 피처 · 가우시안 커널(σ=35°) · 5R×10s · 서버 10Hz · 로컬 LLM(EXAONE 3.5 2.4B)`

---

## 개발 목표 (요구사항 관점)

1. 카메라 외부 파라미터에 **불변한** 다중 인물 자세 일치도 점수화
2. "가만히 서 있으면 100점" 같은 **자명한 공략(degenerate solution) 차단**
3. 센서·연산을 **물리적으로 분산**해도 끊기지 않는 소프트 실시간 보장
4. 무거운 생성형 AI(LLM/TTS)를 게임 루프에 얹되 **프레임 드랍 없이**
5. 설치 없는 브라우저 2-스크린(참가자/관객), **완전 온디바이스**

---

## 개발 결과 (달성 근거)

- **불변 피처 설계** — 8개 관절을 limb 벡터 사잇각으로 계산 → 평행이동·스케일·인물 위치에 불변.
- **확률적 유사도 + 반-치팅 게이트** — 임계값이 아닌 가우시안 커널 + 표현력 게이팅.
- **결정론적 상태머신** — `idle→intro→countdown(3s)→playing(10s)→result(4s)→finished` ×5R, 서버 10Hz 고정 틱·WebSocket 브로드캐스트, 게이지 EMA(α=0.3).
- **분산 센서 파이프라인** — **키포인트(17×3)만** 전송, 워커 내부 캡처/전송/추론 **3스레드 분리**.
- **온디바이스 생성형 AI 진행자** — EXAONE 3.5 2.4B + edge-tts, 전부 게임 루프 밖 백그라운드 태스크.

---

## 핵심 기술 ① 각도-가우시안 유사도 + 활동성 게이트

좌표 회귀가 아닌 **각도 피처 공간의 커널 유사도**로 설계.

- 관절 각도: $\theta_j=\operatorname{atan2}\big(\lVert a\times c\rVert,\ a\cdot c\big)$ (vertex 기준 두 limb 벡터 $a,c$)
- 두 인물 유사도(공통 가시 관절 $J$):

$$S(p,q)=\frac{100}{|J|}\sum_{j\in J}\exp\!\Big(\!-\frac{(\theta_j^{p}-\theta_j^{q})^2}{2\sigma^2}\Big),\quad \sigma=35^\circ$$

- 표현력: $E=\mathrm{clip}\!\big(\tfrac{1}{|J|}\textstyle\sum_j|\theta_j-\theta_j^{\text{rest}}|/45^\circ,\,0,1\big)$
- 활동성 게이트: $g(E)=0.12+0.88\,E$
- **최종 점수**: $\ \text{score}=\bar S\cdot g(E)$ (인물 ≥2일 때만)

---

## 핵심 기술 ① 설계 의도

- **가우시안 커널** — 하드 임계값의 계단 현상 없이 "거의 비슷"을 연속 보상 → 게이지가 자연스럽게 움직임.
- **활동성 게이트** — 모두 차렷이면 $\bar S$가 높아도 $E\approx0$ → 점수 0.12배로 붕괴.
  **degenerate solution을 단순 규칙이 아니라 보상 함수로 차단.**
- **가시성 마스킹**(keypoint score < 0.3 제외)으로 부분 가림에 강건.

> 핵심: "좌표를 맞히는" 문제를 "각도 분포를 합의하는" 문제로 재정의.

---

## 핵심 기술 ② 엣지 추론: MoveNet **int8** 양자화

- MoveNet SinglePose Lightning, 입력 **192×192**, COCO 17-keypoint, `num_threads=4`, tflite-runtime + XNNPACK.
- **완전 정수 양자화 파이프라인 직접 구현**
  - 입력: $q=\mathrm{round}(x/s+z)$ 클리핑
  - 출력: $(q-z)\cdot s$ 역양자화 (float/int8 자동 분기)
- 매 추론 `inference_ms` 자체 계측.

**왜 중요한가** — int8로 메모리·연산을 줄여 **CPU-only 라즈베리파이에서 실시간 추론**을 성립시킨 것이 "온디바이스" 주장의 실체.

---

## 핵심 기술 ② 실측 성능 (라즈베리파이 CPU)

MoveNet int8 · 192×192 · 200 runs · XNNPACK

| 스레드 | p50 | p95 | 처리량(p50) |
|:--:|:--:|:--:|:--:|
| **4 (운영값)** | **15.1 ms** | **17.3 ms** | **~66 fps** |
| 2 | 25.0 ms | 32.5 ms | ~40 fps |
| 1 | 38.9 ms | 43.1 ms | ~26 fps |

- 모델은 4스레드에서 **p50 15ms (~66fps 여유)** → 게임은 5fps로 스로틀해 CPU·대역폭을 LLM/TTS와 공유.
- 재현: `python scripts/benchmark_movenet_int8.py --model models/...int8.tflite --image <img> --runs 200 --num-threads 4`

---

## 핵심 기술 ③ 소프트 실시간 아키텍처

무거운 생성형 AI를 **프레임 드랍 없이** 얹는 설계.

- 서버 **10Hz 결정론 틱**과 LLM/TTS를 **시간적으로 분리**:
  `playing` 구간엔 **절대 호출 안 함**, intro/result/finished에서만 `asyncio.create_task`.
- LLM은 stdlib `urllib` 호출을 `asyncio.to_thread`로 감싸 **이벤트 루프 비차단**, 부팅 시 **워밍업**으로 콜드스타트(~9초) 제거.
- **다단계 graceful degradation** — LLM 실패→정적 텍스트, TTS 실패→Web Speech API.
  각 단계가 독립적으로 무너져도 **게임은 계속**.

---

## 핵심 기술 ④ 분산 시스템·전송 설계

```text
[카메라 워커 N대] ─WS(JPEG+키포인트)→ [FastAPI 서버] ─WS→ [브라우저 ×2]
  · OpenCV 캡처                       · 각도 채점/상태머신     · /game 참가자
  · MoveNet int8 추론                 · 10Hz 브로드캐스트      · /stage 관객
  · 3스레드(캡처/전송/추론)            · LLM·TTS 백그라운드     · 2D MC 아바타
```

- 워커 1대 = 카메라 1대 = 플레이어 1명.
- **키포인트만 전송**(영상은 MJPEG 별도 채널) → 추론 결과/원본을 분리해 대역폭·지연을 독립 제어.
- 서버는 멀티-소스 키포인트를 **틱 단위로 융합·합의**.

---

## 결과 분석 및 기대 효과

- **목표 달성** — ① 불변 채점 ✅ ② degenerate 차단 ✅ ③ 분산 소프트 실시간 ✅ ④ 생성형 AI 무드랍 통합 ✅ ⑤ 완전 온디바이스 ✅
- **측정 지표**
  - 추론: MoveNet int8 **p50 15ms / p95 17ms @4스레드 (~66fps)**
  - 루프: 10Hz 틱 지터(목표 100ms 대비 σ) — [측정]
  - 채점: 키포인트 수신→점수 브로드캐스트 e2e 지연 — [측정]
  - 생성형: LLM 완성 시간(워밍업 전후), TTS 합성 지연·폴백율 — [측정]
- **병목·개선** — 경량 LLM CPU 처리량 한계를 *모델이 아니라 시스템*(시간 분리+백그라운드+워밍업)으로 흡수.
- **기대효과** — 프라이버시(영상이 디바이스를 떠나지 않음)·무비용·오프라인 → 전시/교육/리테일 키오스크 등 엣지 AI 인터랙션 일반 패턴으로 확장.

---

## 향후 연구 과제

- **시간축 도입** — 정지 자세 → 동작 *시퀀스* 정합(DTW/temporal kernel), 타이밍 동기까지 채점.
- **피처/모델 고도화** — 관절 가중치 학습, MoveNet MultiPose로 1카메라 다인 지원, NPU/델리게이트 가속.
- **분산 확장** — 워커 자동 디스커버리, 시간 동기(드리프트 보정), 동시 다중 룸.
- **신뢰성** — 추론·채점 단위 테스트와 CI, 회귀용 합성 포즈 데이터셋, 원클릭 배포.

---

## 프로젝트 수행 후기

- **느낀 점** — 모델 한 개가 아니라 **센서→엣지 추론→분산 융합→게임 로직→웹→음성**까지 전 스택을 직접 닫은(close the loop) 경험.
- **어려웠던 점 & 극복**
  - 카메라 환경 편차 → **좌표 대신 각도-불변 피처**로 정면 돌파.
  - 무거운 LLM/TTS가 실시간을 침범 → **시간적 분리 + 비차단 + 워밍업**으로 구조적 해결.
  - 엣지 자원 제약 → **int8 양자화**로 CPU 실시간 성립.
- **소회** — "모델을 잘 고르는 것"보다 **제약 안에서 시스템으로 성능을 만들어내는 엔지니어링**이 온디바이스 AI의 본질임을 체득.

---

# 감사합니다
### 이구동성 텔레파시 · On-Device AI
데모: `http://<SERVER_IP>:8000/game` · 관객 `…/stage`
