# Python Linting and Formatting

Python 코드의 자동 포매팅과 린팅 정책을 정의한다.

## 기본 도구

- Formatter: `ruff format`
- Linter: `ruff check`
- Import 정렬: Ruff `I` rule
- 자동 수정: `ruff check --fix`

Black, isort, Flake8을 따로 추가하지 않고 Ruff로 통일한다. 특별한 이유로 도구를 추가해야 할 때는 정책 문서에 이유를 남긴다.

## 권장 설정

`pyproject.toml`에 아래 설정을 둔다.

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = [
  "E",    # pycodestyle errors
  "F",    # pyflakes
  "W",    # pycodestyle warnings
  "I",    # isort
  "B",    # flake8-bugbear
  "C4",   # flake8-comprehensions
  "UP",   # pyupgrade
  "SIM",  # flake8-simplify
  "RET",  # flake8-return
  "ARG",  # flake8-unused-arguments
  "PTH",  # flake8-use-pathlib
  "ERA",  # eradicate commented-out code
  "RUF",  # Ruff-specific rules
]
ignore = [
  "E501", # line length is handled by formatter where practical
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
```

## 실행 명령

로컬 개발 중:

```bash
ruff format .
ruff check --fix .
```

커밋 전:

```bash
ruff format --check .
ruff check .
```

## 예외 규칙

- lint rule을 끌 때는 가능한 가장 좁은 범위에서 끈다.
- 파일 전체 ignore는 마지막 수단으로만 사용한다.
- `noqa`를 사용할 때는 rule code를 명시한다.
  - 좋은 예: `# noqa: ARG001`
  - 피할 예: `# noqa`
- 같은 예외가 반복되면 코드 구조나 설정을 재검토한다.
