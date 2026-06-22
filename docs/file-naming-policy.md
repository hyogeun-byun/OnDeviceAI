# File Naming Policy

이 문서는 프로젝트 파일과 디렉터리 이름 규칙을 정의한다.

## 기본 원칙

- 파일명은 역할을 설명해야 한다.
- 이름은 짧고 구체적으로 작성한다.
- 소문자를 기본으로 한다.
- 공백은 사용하지 않는다.
- 의미 없는 축약은 피한다.
- 같은 종류의 파일은 같은 패턴을 따른다.

## 공통 규칙

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 일반 디렉터리 | `kebab-case` 또는 기존 생태계 관례 | `model-assets`, `sample-data` |
| Python 패키지 디렉터리 | `lowercase` 또는 `snake_case` | `vibepose`, `pose_analysis` |
| Python 파일 | `snake_case.py` | `pose_estimator.py` |
| Markdown 문서 | `kebab-case.md` | `git-commit-policy.md` |
| YAML/TOML/JSON 설정 | `kebab-case` | `camera-defaults.yaml` |
| 테스트 파일 | `test_*.py` | `test_pose_score.py` |
| 이미지/샘플 파일 | `kebab-case` | `standing-side-view.png` |
| 모델 파일 | `<model-name>-<variant>-<version>.<ext>` | `rtmpose-tiny-v1.onnx` |

## Python 파일명

- 모듈 파일은 `snake_case.py`를 사용한다.
- 클래스 이름을 그대로 파일명으로 쓰지 않는다.
  - 좋은 예: `pose_estimator.py`
  - 피할 예: `PoseEstimator.py`
- 모듈은 하나의 주된 책임을 가져야 한다.
- 너무 넓은 이름을 피한다.
  - 피할 예: `utils.py`, `helpers.py`, `common.py`
  - 대안: `path_utils.py`, `image_preprocessing.py`, `angle_math.py`

## 문서 파일명

- Markdown 문서는 `kebab-case.md`를 사용한다.
- 문서명은 주제를 명확히 드러낸다.
  - 좋은 예: `python-coding-policy.md`
  - 피할 예: `notes.md`, `rule.md`
- 정책 문서는 가능하면 `*-policy.md` suffix를 사용한다.

## 설정 파일명

- 설정 파일은 `kebab-case`를 사용한다.
- 환경별 설정은 suffix로 구분한다.

예시:

```text
app-defaults.yaml
app-local.example.yaml
camera-defaults.yaml
model-runtime.yaml
```

규칙:

- 실제 비밀값이 들어간 local 설정은 Git에 커밋하지 않는다.
- 예시 설정은 `.example`을 포함한다.
- 기본 설정은 `defaults`를 포함한다.

## 모델과 데이터 파일명

모델 파일:

```text
<model-name>-<variant>-<version>.<ext>
```

예시:

```text
rtmpose-tiny-v1.onnx
rtmpose-small-int8-v1.onnx
```

샘플 데이터:

```text
<subject-or-scene>-<view-or-purpose>.<ext>
```

예시:

```text
standing-front-view.jpg
desk-posture-side-view.mp4
```

## 금지 패턴

- 공백이 있는 이름
- 대소문자가 섞인 애매한 이름
- 날짜만 있는 이름
- `final`, `final2`, `new`, `old`, `temp`
- 의미 없는 약어
- 개인 이름이나 로컬 PC 경로가 드러나는 이름

피할 예:

```text
New File.py
final_model.onnx
test2.py
my_laptop_config.yaml
```

## 예외

외부 도구나 프레임워크가 강제하는 파일명은 예외로 허용한다.

예시:

- `README.md`
- `LICENSE`
- `pyproject.toml`
- `.gitignore`
- `Dockerfile`

예외가 반복되면 이 문서에 명시적인 규칙으로 추가한다.
