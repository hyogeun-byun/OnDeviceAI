# Python Testing Policy

Python 테스트 작성과 실행 정책을 정의한다.

## 기본 도구

- 테스트 프레임워크는 pytest를 사용한다.
- 커버리지는 `pytest-cov`를 사용한다.
- 테스트 파일명은 `test_*.py`로 작성한다.
- 테스트 함수명은 `test_*`로 작성한다.

## 테스트 분류

권장 구조:

```text
tests/
  unit/
  integration/
  performance/
```

분류 기준:

- `unit`: 외부 장치, 모델 파일, GUI 없이 빠르게 실행되는 테스트
- `integration`: 파일 시스템, 모델 로딩, 카메라 adapter 등 경계 테스트
- `performance`: FPS, latency, memory 등 성능 기준 확인

## 작성 원칙

- 핵심 로직은 테스트 가능한 순수 함수나 작은 클래스로 분리한다.
- 카메라, 모델 파일, GPU, GUI에 직접 의존하는 코드는 thin wrapper로 유지한다.
- 외부 의존성은 mock, fake, fixture로 대체한다.
- 버그 수정에는 가능하면 회귀 테스트를 추가한다.
- 테스트 이름은 기대 동작을 설명해야 한다.

좋은 예:

```python
def test_calculate_posture_score_returns_lower_score_for_asymmetric_shoulders() -> None:
    ...
```

## 실행 명령

기본 실행:

```bash
pytest
```

커버리지 포함:

```bash
pytest --cov=src --cov-report=term-missing
```

느린 테스트 제외:

```bash
pytest -m "not slow"
```

## 성능 테스트

- 성능 테스트는 일반 단위 테스트와 분리한다.
- 측정 전 warm-up 구간을 둔다.
- 평균값만 보지 말고 p95 frame time을 함께 본다.
- 성능 기준은 하드웨어와 모델 버전을 함께 기록한다.

권장 지표:

- 평균 FPS
- p95 frame time
- peak memory
- model inference time
- post-processing time
- UI render time
