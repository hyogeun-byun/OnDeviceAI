# Python Coding Policy

이 문서는 Python 코드 정책의 진입점이다. 상세 규칙은 아래 문서로 나누어 관리한다.

## 적용 범위

- Python 애플리케이션 코드
- Python 테스트 코드
- Python 기반 스크립트와 개발 도구 설정
- Python 프로젝트 구조와 품질 자동화

## 기본 원칙

- Python 3.10 이상을 기준으로 한다.
- 새 코드는 타입 힌트를 필수로 작성한다.
- 포매팅과 린팅은 Ruff를 기준으로 자동화한다.
- 타입 검사는 mypy를 기준으로 한다.
- 테스트는 pytest를 기준으로 한다.
- 성능이 중요한 코드는 측정 가능한 구조로 작성한다.
- OpenCV, MMPose, ONNX Runtime, GUI 같은 외부 프레임워크 의존성은 핵심 도메인 로직과 분리한다.

## 세부 문서

- [Python Style Guide](python/python-style-guide.md)
  - 코드 스타일, 네이밍, docstring, import, 주석 규칙
- [Python Linting and Formatting](python/python-linting-and-formatting.md)
  - Ruff formatter/linter 설정과 실행 정책
- [Python Typing Policy](python/python-typing-policy.md)
  - 타입 힌트, mypy, NumPy 타입, `Any` 사용 기준
- [Python Testing Policy](python/python-testing-policy.md)
  - pytest, 테스트 분류, mock/fake, 커버리지 기준
- [Python Runtime Quality Policy](python/python-runtime-quality-policy.md)
  - 에러 처리, 로깅, 성능, 의존성, 보안/개인정보 기준

## 관련 공통 정책

- [Git Commit Policy](git-commit-policy.md)
- [File Naming Policy](file-naming-policy.md)

## 커밋 전 기본 체크

프로젝트 구조가 잡힌 뒤에는 최소한 아래 명령이 통과해야 한다.

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

초기 단계에서 `src`나 테스트 디렉터리가 아직 없다면 실제 구조에 맞게 명령을 조정한다.
