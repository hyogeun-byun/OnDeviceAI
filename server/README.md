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

