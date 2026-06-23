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
