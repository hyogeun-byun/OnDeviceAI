# Python Style Guide

Python 코드의 기본 스타일, 네이밍, import, 주석, docstring 규칙을 정의한다.

## Python 버전

- 기본 버전은 Python 3.10 이상으로 한다.
- 3.10 이상 문법을 사용할 수 있다.
  - `X | None`
  - `match`
  - `typing.TypeAlias`
- 의존성이 허용한다면 Python 3.11 이상을 우선 고려한다.

## 코드 스타일

- 포매터는 Ruff formatter를 사용한다. 구체적인 설정(라인 길이, 따옴표, 들여쓰기, import 정렬)은 [python-linting-and-formatting.md](python-linting-and-formatting.md)를 참조한다.
- 불필요한 축약, 과도한 영리함, 숨은 부작용을 피한다.
- public 함수와 클래스는 의도를 알 수 있는 docstring을 작성한다.
- 복잡한 로직에는 "무엇"이 아니라 "왜"를 설명하는 짧은 주석만 남긴다.

## 네이밍 규칙

PEP 8을 기본으로 하되, 아래 규칙을 명시적으로 따른다.

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 패키지 | `lowercase`, 짧게 | `pose`, `vision` |
| 모듈 파일 | `snake_case.py` | `pose_estimator.py` |
| 함수 | `snake_case` | `estimate_pose()` |
| 변수 | `snake_case` | `frame_index` |
| 클래스 | `PascalCase` | `PoseEstimator` |
| 예외 클래스 | `PascalCase`, `Error` suffix | `ModelLoadError` |
| 상수 | `UPPER_SNAKE_CASE` | `DEFAULT_FPS` |
| 타입 별칭 | `PascalCase` | `KeypointArray` |
| private 멤버 | `_leading_underscore` | `_load_model()` |
| 테스트 파일 | `test_*.py` | `test_pose_estimator.py` |
| 테스트 함수 | `test_*` | `test_estimate_pose_returns_keypoints()` |

추가 규칙:

- Boolean 변수와 함수는 의미가 드러나는 이름을 사용한다.
  - 좋은 예: `is_ready`, `has_camera`, `should_skip_frame`
  - 피할 예: `ready_flag`, `camera_check`
- 단위가 있는 값은 이름에 단위를 포함한다.
  - 예: `timeout_seconds`, `frame_interval_ms`, `memory_limit_mb`
- OpenCV/NumPy 배열은 역할을 드러내는 이름을 사용한다.
  - 예: `rgb_frame`, `bgr_frame`, `keypoints_xy`, `scores`
- 약어는 널리 쓰이는 경우만 허용한다.
  - 허용: `fps`, `id`, `url`, `api`, `rgb`, `bgr`, `onnx`
  - 그 외에는 단어를 풀어 쓴다.

## Import 규칙

import 순서는 Ruff의 `I` rule에 맡긴다.

권장 그룹:

1. 표준 라이브러리
2. 서드파티 라이브러리
3. 프로젝트 내부 모듈

규칙:

- wildcard import는 금지한다.
- 순환 import를 만들지 않는다.
- import 시점에 무거운 모델 로딩이나 장치 초기화를 수행하지 않는다.
- 선택적 의존성은 사용하는 함수나 클래스 경계에서 import할 수 있다.

## Docstring

- public 모듈, 클래스, 함수에는 docstring을 작성한다.
- 내부 helper 함수는 이름과 타입으로 의도가 충분하면 생략할 수 있다.
- docstring은 구현 세부보다 계약과 제약을 설명한다.

예시:

```python
def calculate_posture_score(angles: dict[str, float]) -> float:
    """Return a posture score from 0 to 100 based on normalized joint angles."""
```

## 주석

- 코드가 무엇을 하는지는 코드 자체로 표현한다.
- 주석은 왜 이 방식이 필요한지 설명할 때 사용한다.
- 사용하지 않는 코드를 주석으로 남기지 않는다.
- 임시 작업은 `TODO`보다 이슈나 작업 항목으로 추적한다.
