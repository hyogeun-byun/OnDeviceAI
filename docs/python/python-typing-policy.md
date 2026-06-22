# Python Typing Policy

Python 타입 힌트와 정적 타입 검사 정책을 정의한다.

## 기본 원칙

- 새 Python 코드는 타입 힌트를 필수로 작성한다.
- 함수 인자와 반환값에는 타입을 명시한다.
- `Any`는 외부 라이브러리 경계, 점진적 마이그레이션, 정말 불가피한 경우에만 사용한다.
- `Optional[T]`보다 `T | None`을 사용한다.
- 리스트와 딕셔너리는 내장 제네릭을 사용한다.
  - 예: `list[Pose]`, `dict[str, float]`

## 구조화된 타입

- 복잡한 `dict` 대신 가능한 경우 구조화된 타입을 사용한다.
  - `dataclass`
  - `TypedDict`
  - `NamedTuple`
  - 설정/검증이 필요한 경우 `pydantic` 모델
- 함수가 여러 값을 반환하면 의미 있는 타입으로 묶는다.
- 도메인 개념은 원시 타입만으로 흘려보내지 않는다.

예시:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PostureScore:
    value: float
    warnings: list[str]
```

## NumPy와 OpenCV 타입

- NumPy 배열은 가능하면 `numpy.typing.NDArray`를 사용한다.
- 배열 이름에는 좌표계, 색상 채널, 단위가 드러나게 한다.
- OpenCV의 BGR/RGB 차이는 이름으로 명시한다.

예시:

```python
from numpy.typing import NDArray


def calculate_angle(points_xy: NDArray, joint_name: str) -> float:
    ...
```

## mypy

타입 검사는 mypy를 사용한다.

- 새로 작성하는 애플리케이션 코드는 mypy 통과를 목표로 한다.
- 외부 라이브러리 타입이 부족한 경우 최소 범위로 ignore를 둔다.
- `# type: ignore`를 사용할 때는 에러 코드를 포함한다.
  - 예: `# type: ignore[import-untyped]`

권장 설정:

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
strict_equality = true
show_error_codes = true
```

## 금지 또는 제한

- 새 코드에서 타입 없는 public 함수 작성 금지
- 무의미한 `object`, `Any`, `dict`, `list` 남용 금지
- 타입 검사를 통과시키기 위한 과도한 `cast` 사용 금지
- 런타임 동작을 숨기는 동적 attribute 추가 지양
