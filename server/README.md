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

`/game` 경로에서 이구동성 게임을 진행한다. 공용 화면 1개를 프로젝터/모니터에 띄우고, 플레이어(카메라)들은 서로의 영상을 보지 않고 게이지만 본다.

```text
http://<SERVER_IP>:8000/game
```

진행 방식:

- 총 5문제. 각 라운드는 카운트다운 → 동작(15초) → 결과 순으로 자동 진행한다.
- 제시어를 보고 플레이어들이 같은 동작을 취할수록 가운데 텔레파시 게이지가 실시간으로 올라간다.
- 점수는 카메라들이 보내는 MediaPipe 키포인트로 계산한 **관절 각도 유사도**(8개 관절) 기반이라 카메라 위치/거리에 강건하다.
- 라운드 종료 시점의 게이지가 그 라운드 최종 점수가 되고, 5라운드 평균이 최종 텔레파시 점수다.

게임은 서버가 `/api/game/ws` WebSocket으로 상태를 실시간 브로드캐스트하고, `POST /api/game/start`로 시작/재시작한다. 제시어와 라운드 시간 등은 `app/services/game_manager.py` 상단 상수에서 바꿀 수 있다.

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

게임 시작 화면에서 테마(기본/좀비/K-POP/출근길 등)를 고르면 해당 테마의 제시어가 생성된다. "기본" 테마는 항상 고정 제시어를 사용한다. 응답이 결과(6초) 화면 안에 안 들어오면 모델을 더 작은 것으로 바꾸거나 `LLM_TIMEOUT`/`max_tokens`를 줄인다.

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
