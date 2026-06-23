# OnDeviceAI Camera Worker

카메라가 연결된 라즈베리파이에서 실행하는 클라이언트 코드다.

## 설치

```bash
cd camera-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 실행

`.env`에서 `SERVER_URL`을 Web 서버 라즈베리파이 IP로 바꾼 뒤 실행한다.

```bash
python -m app.main
```

예:

```text
SERVER_URL=http://192.168.0.10:8000
CAMERA_ID=camera_01
CAMERA_INDEX=0
```

