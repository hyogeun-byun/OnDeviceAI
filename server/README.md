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
