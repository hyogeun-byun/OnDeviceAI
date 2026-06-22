# Git Commit Policy

이 문서는 Git 커밋 메시지, 브랜치, 커밋 단위 정책을 정의한다.

## 기본 원칙

- 커밋은 하나의 의도 있는 변경 단위로 만든다.
- 서로 다른 목적의 변경을 한 커밋에 섞지 않는다.
- 커밋 메시지만 보고 변경 이유와 범위를 대략 이해할 수 있어야 한다.
- 생성물, 캐시, 로컬 환경 파일은 커밋하지 않는다.

## 커밋 메시지 형식

Conventional Commits를 사용한다.

```text
<type>(<scope>): <summary>
```

예시:

```text
feat(vision): add pose estimator interface
fix(config): handle missing model path
docs(policy): add python linting rules
test(domain): cover posture score edge cases
```

## Type 규칙

| type | 사용 시점 |
| --- | --- |
| `feat` | 사용자 관점의 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 포매팅 등 동작 변경 없는 스타일 수정 |
| `refactor` | 기능 변화 없는 구조 개선 |
| `perf` | 성능 개선 |
| `test` | 테스트 추가/수정 |
| `build` | 빌드, 패키징, 의존성 변경 |
| `ci` | CI 설정 변경 |
| `chore` | 기타 유지보수 작업 |
| `revert` | 이전 커밋 되돌리기 |

## Scope 규칙

scope는 변경 영역을 짧게 적는다.

권장 scope:

- `app`
- `domain`
- `vision`
- `ui`
- `config`
- `models`
- `tests`
- `docs`
- `policy`
- `build`

scope가 애매하면 생략할 수 있다.

```text
chore: initialize project metadata
```

## Summary 규칙

- 영어 소문자 동사 원형으로 시작한다.
- 마침표를 붙이지 않는다.
- 72자 이내를 권장한다.
- 무엇을 했는지보다 왜 의미 있는 변경인지 드러낸다.

좋은 예:

```text
fix(vision): preserve bgr frame order before inference
```

피할 예:

```text
fix: bug fix
update files
작업함
```

## Body와 Footer

필요할 때만 body를 작성한다.

body에는 다음을 적는다.

- 변경 배경
- 설계 선택 이유
- 영향 범위
- 테스트 결과

Breaking change가 있으면 footer에 명시한다.

```text
BREAKING CHANGE: replace legacy config keys with nested camera settings
```

## 커밋 단위

한 커밋에 함께 들어가도 되는 변경:

- 기능 코드와 해당 테스트
- 버그 수정과 회귀 테스트
- 문서 변경과 문서 내부 링크 정리

분리해야 하는 변경:

- 리팩터링과 기능 추가
- 포매팅 대량 변경과 로직 변경
- 의존성 업데이트와 기능 구현
- README 정리와 런타임 코드 변경

## 브랜치 이름

권장 형식:

```text
<type>/<short-description>
```

예시:

```text
feat/pose-estimator
fix/model-path-validation
docs/python-policy
refactor/config-loader
```

규칙:

- 소문자와 하이픈을 사용한다.
- 공백, 한글, 특수문자는 사용하지 않는다.
- 너무 긴 설명은 피한다.

## 커밋 전 체크리스트

- 관련 테스트를 실행했는가
- lint와 format 검사를 통과했는가
- 타입 검사를 통과했는가
- 불필요한 파일이 포함되지 않았는가
- 비밀값, 모델 원본, 대용량 산출물이 포함되지 않았는가
- 커밋 메시지가 변경 의도를 설명하는가
