# VibePose — 온디바이스 AI 실시간 자세 교정

**"8GB RAM에서도 30FPS 보장"**  
MMPose 기반 바디 키포인트를 활용한 **완전 온디바이스** 실시간 자세 교정 프로그램

![VibePose Banner](https://via.placeholder.com/1200x400/0A0A0A/00FFAA?text=VibePose+%7C+On-Device+AI+Posture+Corrector)

### ✨ 한 줄 소개
AI의 완전한 Vibe로 코딩된, **가벼우면서도 강력한** 온디바이스 자세 교정 도구. 클라우드 없이 로컬에서 모든 것이 돌아갑니다.

## 🚀 주요 특징

- ⚡ **30FPS+ 실시간 동작** (8GB RAM 환경 보장)
- 🧬 **MMPose** (RTMPose 기반) 고정밀 바디 키포인트 검출
- 🔍 **지능형 자세 분석** — 어깨, 목, 허리, 골반 등 주요 각도 계산 및 이상 감지
- 📊 **실시간 자세 점수 시스템** (0~100점)
- 🖼️ **시각적 피드백** — 키포인트 오버레이 + 교정 가이드 라인 + 알림
- 🔒 **완전 온디바이스** — 인터넷 연결 불필요, 프라이버시 100% 보호
- 🎨 **모던하고 Vibe 넘치는 UI/UX**
- 🛠️ **최적화 극한까지** — 모델 양자화, 효율적 파이프라인, 최소 리소스 사용

## 🛠️ 기술 스택

- **언어**: Python 3.10+
- **포즈 추정**: MMPose (OpenMMLab) — RTMPose
- **추론 최적화**: ONNX Runtime + Quantization
- **컴퓨터 비전**: OpenCV, NumPy
- **UI**: Dear PyGui (고성능·저자원)
- **코드 스타일**: Clean Architecture + Type Hint + 모듈러 디자인 (AI Vibe 풀충전)

## 📥 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/yourusername/vibepose.git
cd vibepose

# 2. 가상환경 생성 & 활성화
python -m venv venv
source venv/bin/activate    # Windows는 venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 실행
python main.py
