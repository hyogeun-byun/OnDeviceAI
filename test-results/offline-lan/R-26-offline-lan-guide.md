# R-26 오프라인 LAN 동작 검증 가이드

## 검증 목적

하나의 공유기를 내부 LAN으로만 사용하고, 외부 인터넷이 끊긴 상태에서도 카메라 워커, 서버, 브라우저 게임 화면이 정상 동작하는지 보여준다.

성공 기준은 다음과 같다.

- 공유기 WAN 또는 인터넷 연결이 차단되어 있다.
- 서버 보드, 카메라 워커, 브라우저 장치는 같은 공유기 내부 LAN에 연결되어 있다.
- 카메라 워커는 서버의 LAN IP로 WebSocket 연결에 성공한다.
- 대시보드에서 카메라 Online, pose_fps, frame_fps가 표시된다.
- `/game`과 `/stage`가 같은 게임 상태를 표시한다.
- edge-tts 등 외부 TTS가 없어도 정적 텍스트 또는 브라우저 폴백으로 게임이 멈추지 않는다.
- 5라운드 게임이 끝까지 완료된다.

## 권장 오프라인 설정

서버 `.env`는 외부 네트워크 의존성을 끄고 검증한다.

```dotenv
LLM_ENABLED=false
TTS_ENABLED=false
EDGE_TTS_ENABLED=false
```

로컬 Ollama까지 함께 보여줄 경우에만 다음처럼 로컬 엔드포인트를 사용한다.

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=http://127.0.0.1:11434/v1/chat/completions
LLM_MODEL=exaone3.5:2.4b
EDGE_TTS_ENABLED=false
```

카메라 워커 `.env`는 서버 보드의 LAN IP를 가리킨다.

```dotenv
SERVER_URL=http://<SERVER_LAN_IP>:8000
CAMERA_ID=camera_01
POSE_ENABLED=true
```

## 시연 영상 순서

1. 공유기 WAN 케이블이 빠져 있거나 인터넷 연결이 없는 상태를 보여준다.
2. 서버에서 인터넷 연결 실패를 보여준다.
3. 서버의 LAN IP를 확인한다.
4. 카메라 워커에서 서버 LAN IP로 ping 성공을 보여준다.
5. 카메라 워커를 실행하고 WebSocket 연결 및 metrics 로그를 보여준다.
6. 브라우저에서 `http://<SERVER_LAN_IP>:8000`, `/game`, `/stage`에 접속한다.
7. 대시보드에서 카메라 Online, keypoint count, pose_fps를 보여준다.
8. 게임을 시작해 5라운드가 끝까지 완료되는 장면을 보여준다.
9. 결과 화면과 최종 점수가 표시되는 장면을 보여준다.

## 영상에 넣으면 좋은 명령

서버 보드:

```bash
hostname -I
ping -c 3 8.8.8.8
curl http://127.0.0.1:8000/api/game/state
```

카메라 워커:

```bash
ping -c 3 <SERVER_LAN_IP>
python -m app.main
```

기대 결과:

- `ping 8.8.8.8` 실패: 외부 인터넷 차단 증거
- `ping <SERVER_LAN_IP>` 성공: 내부 LAN 통신 증거
- 카메라 워커 로그에 frame_fps, pose_fps, failed_frames, failed_poses 표시
- 게임 화면에서 5라운드 완주

## 제출 증빙 위치

실제 시연 후 아래 파일을 추가하면 R-26 증빙이 더 강해진다.

```text
test-results/offline-lan/server-offline-lan.log
test-results/offline-lan/camera-01-offline-lan.log
test-results/offline-lan/camera-02-offline-lan.log
test-results/offline-lan/camera-03-offline-lan.log
```

최종 평가는 시연영상의 R-26 구간과 위 로그를 평가자가 함께 확인한다.
