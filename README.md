# 이구동성 텔레파시 — 온디바이스 AI 파티 게임

제시어를 보고 **똑같은 동작**을 취하세요. 서로의 모습은 볼 수 없습니다. 오직 **텔레파시**만이 진실을 말합니다.

AI가 실시간으로 여러 사람의 자세를 분석해 텔레파시 게이지를 계산하고, LLM 진행자가 한국어로 코칭 멘트를 던지는 **완전 온디바이스 AI 파티 게임**입니다.

## 🚀 주요 특징

- 🎮 **2-스크린 파티 게임** — 참가자 화면(`/game`)과 관객 무대 화면(`/stage`) 분리
- 🤸 **실시간 자세 동기화** — MediaPipe Pose Lite로 33 landmarks를 추론, 얼굴 방향 + 상체 6개 bone vector 유사도로 텔레파시 게이지 계산
- 🧠 **온디바이스 LLM 진행자** — EXAONE 3.5 2.4B (Ollama)가 한국어로 실시간 코칭 멘트 생성
- 🔊 **신경망 TTS 음성** — Microsoft edge-tts(`ko-KR-InJoonNeural`)로 자연스러운 한국어 음성 합성
- 🎨 **커스텀 다크 UI** — 오로라 애니메이션 + 글래스모피즘, 외부 CSS 프레임워크 미사용
- 📡 **멀티 보드 분산 구조** — 카메라 워커(라즈베리파이 N대) + 서버 보드를 WebSocket으로 연결
- 🔒 **완전 온디바이스** — 포즈 추론·LLM·음성 합성 모두 로컬, 인터넷 불필요(edge-tts 제외)

## 🏗️ 시스템 구조

```
[카메라 보드 N대]  ──WebSocket(JPEG + 키포인트)──▶  [서버 보드]  ──WebSocket──▶  [브라우저]
  camera-worker                                       FastAPI 서버                  게임 화면 + 음성
  · OpenCV 카메라 캡처                                · 게이지/점수 계산              · /game  참가자
  · MediaPipe Pose Lite (10fps)                      · 게임 상태머신 (10Hz)          · /stage 관객
  · JPEG 인코딩 + 키포인트 전송                       · LLM / TTS 백그라운드          · 2D MC 아바타
                                                     · Ollama (EXAONE 3.5 2.4B)     · mp3 음성 재생
                                                     · edge-tts (InJoonNeural)
```

카메라 워커 1대 = 카메라 1대 = 플레이어 1명. 워커는 영상 전송 스레드와 포즈 추정 스레드를 분리해 포즈 추론이 영상 전송을 막지 않도록 구성합니다.

## 🛠️ 기술 스택

### 백엔드

| 항목 | 기술 | 비고 |
|------|------|------|
| 웹 프레임워크 | **FastAPI** + **Uvicorn** | 비동기 WebSocket · REST API |
| 템플릿 엔진 | **Jinja2** | 서버사이드 렌더링 (HTML 3종) |
| 실시간 통신 | **WebSocket** | 카메라↔서버, 서버↔브라우저 |
| HTTP 클라이언트 | 표준 라이브러리 `urllib` | LLM 호출 (외부 의존 없음) |
| 환경 설정 | **python-dotenv** | `.env` 파일 기반 |

### AI / ML

| 용도 | 모델·엔진 | 위치 | 비고 |
|------|-----------|------|------|
| 자세(포즈) 추정 | **MediaPipe Pose Lite** (`model_complexity=0`, 입력 폭 192px) | 카메라 워커 | 33 landmarks · 라즈베리파이 평균 약 30ms · 게임은 10fps로 스로틀 |
| 동작 유사도 점수 | **규칙 기반** — 얼굴 방향 + 상체 6개 bone vector 코사인 유사도 × 활동성 게이트 | 서버 | 픽셀 좌표 미사용, 카메라 위치·거리에 강건 |
| AI MC 멘트·제시어·리포트 | **EXAONE 3.5 2.4B** (Ollama, OpenAI 호환 엔드포인트) | 서버 보드 Ollama | 한국어 경량 LLM, CPU 추론 (~6 tok/s) |
| 서버 사이드 음성 합성 | **edge-tts** `ko-KR-InJoonNeural` | 서버 → 브라우저 mp3 | Microsoft 신경망 TTS (무료, 인터넷 필요) |
| 음성 합성 폴백 | OpenAI TTS(`gpt-4o-mini-tts`) → Piper → espeak-ng 순 자동 선택 | 서버 보드 | 스피커 부착 시 사용 |
| 브라우저 음성 폴백 | **Web Speech API** | 브라우저 | edge-tts 실패 시 자동 전환 |

### 웹 프론트엔드

| 항목 | 기술 | 비고 |
|------|------|------|
| JavaScript | **Vanilla JS** (ES2020+) | 프레임워크 미사용 |
| CSS | **커스텀 CSS** (CSS Custom Properties) | Tailwind·Bootstrap 미사용 |
| 폰트 | **Google Fonts** — Black Han Sans, Gothic A1, Inter | CDN 로드 |
| 스켈레톤 렌더링 | **HTML Canvas API** | 브라우저에서 직접 키포인트 드로잉 |
| 게임 상태 수신 | **WebSocket** (`/api/game/ws`) | 10Hz 브로드캐스트 |
| 카메라 영상 | `<img>` multipart MJPEG 스트림 | `/api/cameras/{id}/stream` |

### 디자인 컨셉

- **다크 테마** — 배경 `#06070d`, 포인트 컬러 `#00ffc6` (민트) / `#7c5cff` (퍼플) / `#ff4d8d` (핑크)
- **오로라 배경** — 3개 orb를 `filter: blur(70px)` + `mix-blend-mode: screen`으로 부유시켜 애니메이션
- **글래스모피즘** — `rgba(255,255,255,0.04)` 배경 + `rgba(255,255,255,0.1)` 테두리
- 외부 UI 라이브러리(Bootstrap, Tailwind 등) **미사용** — 순수 CSS만으로 구현

### 카메라 워커 (라즈베리파이)

| 항목 | 기술 |
|------|------|
| 카메라 캡처 | **OpenCV** (`cv2.VideoCapture`) |
| 포즈 추정 | **MediaPipe Pose Lite** (`mediapipe==0.10.18`) |
| 프레임 인코딩 | JPEG (`cv2.imencode`) |
| 서버 통신 | **websocket-client** 1.8.0 |
| 스레드 구조 | 캡처 / 영상 전송 / 포즈 추정 3개 스레드 분리 |

## ⚙️ 구현 상세

### 포즈 → 점수 계산

워커가 MediaPipe Pose Lite로 뽑은 **33개 landmark**를 서버로 전송합니다(영상은 표시용 JPEG 별도). 서버는 얼굴 방향(head_left/head_right)과 양팔 상체 4개 segment를 합친 **6개 bone vector**를 구해 플레이어 간 코사인 유사도 평균을 냅니다. 여기에 **활동성 게이트**를 곱해 "모두 가만히 서 있으면 유사도가 높아도 낮은 점수"가 되도록 설계해 꼼수를 방지합니다.

### LLM 연동

`app/services/llm_client.py`가 표준 라이브러리(`urllib`)로 Ollama의 OpenAI 호환 엔드포인트를 호출합니다. 블로킹 호출은 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않습니다. 서버 기동 시 워밍업 호출을 보내 **첫 게임 콜드 스타트(~9초)를 제거**합니다. LLM이 느리거나 실패하면 정적 텍스트로 폴백하고 게임은 계속 진행됩니다.

### TTS 음성

edge-tts로 합성한 mp3를 `/api/game/speech/{id}.mp3`로 제공하고, 브라우저가 `<Audio>` API로 재생합니다. `speech_id`로 중복 재생을 방지하며, 실패 시 브라우저 Web Speech API로 자동 폴백합니다. 2D MC 아바타는 음성 재생 중 말풍선·입 애니메이션이 동작합니다.

### 실시간 게임 상태머신

서버가 10Hz로 `idle → intro → countdown → playing(10s) → result → finished` 상태를 구동하고, 매 틱마다 스냅샷을 WebSocket으로 브로드캐스트합니다. **LLM과 음성 합성은 `playing` 구간에서 절대 호출하지 않고** 인트로·결과·종료 구간에서만 `asyncio` 백그라운드 태스크로 실행해 포즈 추론과 게임 루프가 끊기지 않도록 보장합니다.

## 📥 설치 및 실행

### 서버

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../config/server.example.yaml .env  # 환경 변수 설정
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 카메라 워커 (라즈베리파이마다 실행)

```bash
cd camera-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# .env에서 SERVER_URL, CAMERA_ID 설정 후
python -m app.main
```

### 화면 접속

```
http://<SERVER_IP>:8000        # 대시보드
http://<SERVER_IP>:8000/game   # 참가자 화면 (노트북/태블릿)
http://<SERVER_IP>:8000/stage  # 관객 화면 (프로젝터/대형 모니터)
```
