# OnDeviceAI Server

Web 대시보드와 카메라 프레임 수신을 담당하는 서버다.

## 설치

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 접속한다.

```text
http://<SERVER_IP>:8000
```

예:

```text
http://192.168.0.10:8000
```

카메라 워커가 포즈 추정 결과를 보내면 대시보드의 각 카메라 칸에 사람 감지 여부와 keypoint 개수가 표시된다.

## 이구동성 텔레파시 게임

플레이어 화면과 관객 화면을 **분리한 2-스크린** 파티 게임이다.

| 화면 | 경로 | 용도 | 특징 |
|------|------|------|------|
| 참가자 화면 | `/game` | 플레이어용 (노트북/태블릿) | 게이지 + AI MC 코칭만 표시. **영상·다른 사람 동작은 안 보임** (서로 못 보고 텔레파시로만 맞춤). 음성 코칭 재생. |
| 관객 화면 | `/stage` | 프로젝터/대형 모니터 | 모든 카메라 **실시간 영상** + 게이지 + 코칭 + 점수판 + 카운트다운/점수 오버레이. |

```text
http://<SERVER_IP>:8000/game     # 참가자
http://<SERVER_IP>:8000/stage    # 관객(무대)
```

진행 방식:

- 시작 화면에서 **카테고리** 1개를 고른다: `상황 / 운동 / 감정 / 인물 / 영화 혹은 애니메이션`
- 게임이 시작되면 선택한 카테고리 안에서 **랜덤 제시어 5개**가 뽑힌다.
- 총 5문제. 각 라운드는 카운트다운(3s) → 동작(**10초**) → 결과(4s) 순으로 자동 진행한다.
- 제시어를 보고 플레이어들이 같은 동작을 취할수록 가운데 텔레파시 게이지가 실시간으로 올라간다.
- 점수는 MoveNet 키포인트의 **관절 각도 유사도**(8개 관절)에 **활동성 게이트**를 곱한다. 다 같이 **가만히 서 있으면**(중립 자세) 유사도가 높아도 점수가 낮게 깔려서, 가만히 있는 “꼼수”를 막고 과감한 동작을 유도한다.
- **AI MC 코칭**: 동작 중 게이지/활동성/플레이어별 싱크를 보고 실시간 멘트를 내보낸다. 한 명만 따로 놀면 `"3번님! 다른 분들과 동작이 좀 달라요"` 처럼 콕 집어준다. 멘트가 정신없지 않도록 **한 멘트는 최소 4초 유지**하고, 브라우저 음성도 최소 간격을 두고 읽는다. (이 코칭 음성은 LLM이 아니라 **브라우저 Web Speech**라 동작 인식 성능에 영향이 없다.)
- 라운드 종료 **시점의 게이지**가 그 라운드 최종 점수가 되고(마지막 순간의 동작이 점수), 5라운드 평균이 최종 텔레파시 점수다.
- 헤더의 **`↺ 처음부터`** 버튼으로 게임 중 언제든 처음(시작 화면)으로 되돌려 다시 시작할 수 있다.

게임은 서버가 `/api/game/ws` WebSocket으로 상태를 실시간 브로드캐스트하고, `POST /api/game/start`(카테고리 전달)로 시작, `POST /api/game/begin`으로 첫 라운드 진입, `POST /api/game/reset`으로 처음으로 되돌린다. 제시어와 라운드 시간 등은 `app/services/game_manager.py` 상단 상수에서 바꿀 수 있다.


## 사용한 모델과 구현 방식 (한눈에)

### 전체 구성

```text
[카메라 보드 N개]  --WebSocket(JPEG+키포인트)-->  [서버 보드]  --WebSocket-->  [브라우저/프로젝터]
  camera-worker                                   FastAPI 서버                  게임 화면 + 음성
  · 카메라 캡처                                    · 게이지/점수 계산              · 2D MC 아바타
  · MoveNet int8(TFLite)                          · 게임 상태머신(10Hz)          · mp3 음성 재생
  · 5fps 키포인트 추론                             · LLM/TTS 백그라운드           · 결과 PNG 저장
                                                  · Ollama(LLM) + edge-tts(음성)
```

- **카메라 워커**와 **서버**는 분리된 프로세스/보드다. 카메라 1대 = 워커 1개이고, 워커는 `CAMERA_ID`로 서버에 붙는다.
- LLM과 음성 합성은 **실시간 동작 인식(playing) 구간에서는 절대 호출하지 않고** 인트로/결과/종료 구간에서만 `asyncio` 백그라운드 태스크로 돈다. 그래서 포즈 추론·게임 루프는 어떤 경우에도 끊기지 않는다. 실패 시 모두 정적 텍스트로 폴백한다.

### 사용한 모델

| 용도 | 모델 / 엔진 | 위치 | 비고 |
|------|-------------|------|------|
| 자세(포즈) 추정 | **MoveNet SinglePose Lightning** (TFLite **int8**, 192×192) | 카메라 워커 | COCO 17 keypoint, CPU 추론 p50 15ms/p95 17ms(4스레드) · 게임은 5fps로 스로틀(영상 전송과 스레드 분리) |
| 동작 유사도 점수 | 규칙 기반(모델 아님) — **관절 각도 8개 코사인 유사도 × 활동성 게이트** | 서버 | `app/services/pose_similarity.py`, 카메라 거리/위치에 강건 · 가만히 있으면 저점 |
| AI MC 멘트·제시어·리포트 | **EXAONE 3.5 2.4B** (Ollama, OpenAI 호환) | 서버 보드의 Ollama | 한국어 경량 LLM, CPU 추론(~6 tok/s) |
| 자연스러운 한국어 음성 | **edge-tts** 신경망 보이스 `ko-KR-InJoonNeural` | 서버→브라우저 mp3 | 무료, 인터넷 필요, 노트북/헤드폰 재생용 |
| 보드 스피커 음성(선택) | OpenAI TTS / Piper / espeak-ng 자동 선택 | 서버 보드 | 스피커가 달린 경우 |

### 구현 방식 요약

1. **포즈 → 점수**: 워커가 MoveNet으로 뽑은 키포인트(COCO 17점)만 서버로 보낸다(영상은 표시용 JPEG 별도). 서버는 각 사람의 8개 관절 각도 벡터를 만들고, 플레이어들 간 각도 유사도를 평균해 0~100 "텔레파시 게이지"로 환산한다. 픽셀 좌표가 아니라 **각도**를 쓰므로 카메라 위치·거리·키 차이에 강하다.
2. **게임 상태머신**: 서버가 10Hz로 `idle → intro → countdown → playing(10s) → result → finished` 를 구동하고 매 틱마다 스냅샷을 WebSocket으로 브로드캐스트한다. 멘트와 라운드 시작을 분리하려고 `intro` 단계와 `POST /api/game/begin` 트리거를 뒀다. `POST /api/game/reset` 으로는 진행 중이던 게임을 버리고 시작 화면으로 되돌린다.
3. **LLM 연동**: `app/services/llm_client.py` 가 표준 라이브러리(urllib)로 Ollama의 OpenAI 호환 엔드포인트를 호출하고, 블로킹 호출은 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않는다. 서버 시작 시 한 번 워밍업 호출을 보내 **첫 게임 콜드 스타트(~9초)를 제거**한다.
4. **CPU 속도 대응**: 결과 구간은 4초로 짧고 CPU LLM은 느리므로, 결과 진입 즉시 정적 멘트를 보여주고 말하고, LLM 멘트가 제때 오면 **화면 텍스트만 조용히 교체**한다(음성 중복 방지). 시간 제한이 없는 **인트로 인사**와 **최종 리포트**가 LLM+음성의 주 무대다.
5. **음성**: edge-tts로 합성한 mp3를 `/api/game/speech/{id}.mp3` 로 제공하고 브라우저가 받아 재생한다(`speech_id`로 중복 재생 방지, 실패 시 브라우저 Web Speech로 폴백). 2D MC 아바타는 음성 재생 중 입모양·말풍선이 움직인다.
6. **리포트**: 종료 시 베스트/최저 라운드의 동작 스냅샷·제시어·점수를 모아 1080×1350 캔버스에 그려 **PNG 한 장으로 저장**할 수 있다.

> 실제 이번 구성에서는 Ollama를 별도 보드가 아니라 **서버 보드에 같이** 설치해 systemd 서비스로 자동 구동했다(`exaone3.5:2.4b`, `LLM_TIMEOUT=30`). 카메라를 같은 보드에서 로컬로 받을 때는 서버+LLM+포즈가 CPU를 나눠 쓰므로 워커 `FPS`를 8~12로 낮추는 것을 권장한다.

### LLM 진행자 (선택)

경량 LLM을 붙이면 라운드 사이에 AI MC 멘트, 테마별 동적 제시어, 최종 텔레파시 궁합 리포트가 생성된다. LLM은 **실시간(playing) 구간에서는 호출하지 않고** 카운트다운/결과/종료 구간에서만 백그라운드로 돌기 때문에 포즈 추론 성능에는 영향을 주지 않는다. LLM이 꺼져 있거나 응답이 없으면 정적 텍스트로 자동 폴백하므로 게임은 그대로 동작한다.

권장 구성은 라즈베리파이 1대를 **LLM 전용 보드**로 두고 [Ollama](https://ollama.com)를 OpenAI 호환 모드로 띄우는 것이다.

```bash
# LLM 전용 보드에서
curl -fsSL https://ollama.com/install.sh | sh
ollama pull exaone3.5:2.4b        # 한국어 경량 모델 (또는 qwen2.5:3b)
OLLAMA_HOST=0.0.0.0 ollama serve  # LAN 노출 (기본 포트 11434)
```

서버 `.env`에서 활성화한다.

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=http://<LLM_BOARD_IP>:11434/v1/chat/completions
LLM_MODEL=exaone3.5:2.4b
LLM_TIMEOUT=12
LLM_DEFAULT_THEME=기본
```

게임 시작 화면에서 테마(기본/좀비/K-POP/출근길 등)를 고르면 해당 테마의 제시어가 생성된다. "기본" 테마는 항상 고정 제시어를 사용한다. 응답이 결과(4초) 화면 안에 안 들어오면 모델을 더 작은 것으로 바꾸거나 `LLM_TIMEOUT`/`max_tokens`를 줄인다.

> 32GB(8GB×4) 분산: 더 큰 모델(14B+)을 쓰고 싶으면 노는 보드들을 llama.cpp `rpc-server`로 묶어 샤딩할 수 있다. 다만 네트워크 지연이 있어 결과/종료 구간 전용으로만 권장하며, 카메라가 도는 보드는 playing 중 CPU 충돌을 피하기 위해 샤드에서 제외한다.

### AI MC 음성(TTS, 선택)

AI MC 멘트와 최종 리포트를 **스피커가 달린 서버 보드**에서 음성으로 출력한다. TTS도 LLM처럼 **playing 구간에서는 호출하지 않고** 시작 인트로/결과/종료 구간에서만, 그것도 백그라운드 큐 워커 스레드에서 합성·재생하므로 게임 루프와 포즈 추론을 막지 않는다. 합성에 실패하면 다음 엔진으로 폴백하고, 다 안 되면 화면 멘트만 나온다.

특정 실존 인물의 목소리/말투는 모방하지 않으며 "밝은 예능 MC 톤 + AI MC 민수" 컨셉으로 동작한다.

엔진은 `TTS_ENGINE=auto`일 때 사용 가능한 것 중 품질 높은 순으로 자동 선택한다: **OpenAI TTS → Piper → espeak-ng**.

```bash
# 가장 가벼운 즉시 테스트(오프라인, 로봇 톤): espeak-ng
sudo apt install -y espeak-ng mpg123 alsa-utils

# 오프라인 고품질: Piper (모델 .onnx 다운로드 후 경로 지정)
#   https://github.com/rhasspy/piper  (ko_KR 음성 모델 받기)

# 최고 품질(온라인, 키 필요): OpenAI TTS
pip install openai            # server/.venv 안에서
export OPENAI_API_KEY=sk-...  # 서버 실행 환경에 설정
```

서버 `.env`:

```dotenv
TTS_ENABLED=true
TTS_ENGINE=auto            # 또는 openai / piper / espeak
TTS_VOICE=coral            # OpenAI voice
TTS_OPENAI_MODEL=gpt-4o-mini-tts
TTS_PIPER_MODEL=/home/willtek/piper/ko_KR-voice.onnx
TTS_LANG=ko
TTS_TEAM_NAME=             # 비우면 "여러분"
TTS_MC_NAME=민수
```

스피커는 발표 안정성 기준 **유선(AUX) > HDMI > 블루투스** 순으로 권장한다. 출력 점검:

```bash
speaker-test -t wav -c 2     # 스피커 소리 확인
espeak-ng -v ko "테스트입니다"  # espeak 동작 확인
```

### 노트북에서 자연스러운 목소리 듣기 (edge-tts, 브라우저 재생)

보드 스피커 없이 **노트북/헤드폰**으로 자연스러운 한국어 음성을 듣고 싶을 때 쓴다. 서버가 Microsoft Edge의 **무료 신경망 보이스(edge-tts)** 로 음성을 합성해 `/api/game/speech/{id}.mp3` 로 제공하고, 브라우저가 이를 받아 재생한다. 합성은 실시간 경로 밖(인트로/결과/종료)에서 백그라운드로만 일어나므로 포즈 추론을 막지 않는다.

```bash
pip install edge-tts          # server/.venv 안에서 (requirements.txt에 포함)
```

서버 `.env`:

```dotenv
EDGE_TTS_ENABLED=true
EDGE_TTS_VOICE=ko-KR-InJoonNeural   # 또는 ko-KR-SunHiNeural(여)
EDGE_TTS_RATE=+8%
```

- **인터넷 연결**이 필요하다(음성 합성 시 Edge 서비스 호출). 안 되면 브라우저 기본 음성(Web Speech)으로 자동 폴백한다.
- 노트북 브라우저에서 `http://<server-ip>:8000/game` 접속 → **게임 시작** 클릭(이 클릭이 오디오 재생 권한을 풀어줌) → 헤드폰으로 조용히 청취. 우상단 🔊/🔇로 음소거.

### 게임 진행 흐름 (인트로 → 시작 트리거 → 라운드 → 리포트)

1. **idle**: 테마 선택 후 `게임 시작`.
2. **intro**: AI MC 민수(2D 애니메이션 아바타)가 인사·멘트. 준비되면 `시작하기 ▶` 를 눌러야 라운드가 시작된다(멘트와 게임 시작이 분리됨).
3. **라운드 5판**: 제시어는 **추상 단어**(사랑/승리/공포…)라서 해석이 자유롭다. LLM이 켜져 있고 테마가 "기본"이 아니면 테마에 맞는 추상 단어를 생성한다.
4. **finished**: 베스트 호흡 라운드 / 텔레파시 대참사(최저 점수) 라운드를 동작 스냅샷·단어·점수와 함께 보여주고, `📸 결과 이미지 저장` 으로 PNG 한 장으로 저장해 갈 수 있다.



서버는 카메라별 수신 상태를 `server_metrics` 로그로 출력한다.

```text
recv_frame_fps: 서버가 실제로 받은 프레임 FPS
recv_pose_fps: 서버가 실제로 받은 포즈 결과 FPS
recv_kb_s: 서버가 받은 초당 이미지 데이터량
avg_frame_kb: 서버가 받은 프레임 1장 평균 크기
```

성능 시각화는 기본으로 켜져 있다. 끄려면 `server/.env`에 다음 값을 넣는다.

```text
VISUALIZE_METRICS=false
```
