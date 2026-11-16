# 원문 검증 → 학습 → 실제 추론 서버 → 사이트 연결

후속 사용자 승인으로 제공 자료 실험용 모델을 실제 학습·실행했습니다. 현재 실험용 사이트/서버는 [EXPERIMENTAL_RUN.md](EXPERIMENTAL_RUN.md)를 사용합니다. 아래는 원문 승인 모델의 별도 엄격한 배포 경로이며 그 승인 수는 아직 0행입니다.

현재 상태: **서버 코드와 연결 경로는 구현됐지만, 실제 연구 모델과 공개 추론 서버는 아직 없습니다.**

원문 53 DOI의 접속을 시도한 결과 전부 환경 네트워크 정책에서 차단됐습니다. `docs/source_access_status.json`은 마지막 시도의 요약입니다. 따라서 새 학습 승인은 0행이며, P-E/PUND 모두 실제 자료 학습은 승인 게이트에서 중단됐습니다. 합성 테스트 모델의 점수를 연구 성능으로 보고하지 않습니다.

## 사용자가 필요한 작업

1. 이 대화의 **환경 설정에서 변경사항을 저장한 다음 Publish**합니다. 논문 원문·DOI 확인에 필요한 도메인은 설정 초안에 이미 저장했습니다. 이는 GitHub Pages의 배포와 다른 설정입니다. 적용 후 에이전트가 원문 다운로드를 다시 시도합니다.
2. 공개 서버를 운영할 계정이 없으므로 **Render 계정 생성·로그인**이 필요합니다. [준비된 배포 설정 열기](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fqotnsdyd19-ux%2F-)로 저장소의 `render.yaml`을 불러올 수 있습니다. 설정은 `free` 플랜을 지정합니다. 실제 계정 화면에서 무료 조건을 확인하고 유료 플랜을 임의 선택하지 마세요. 원문 검증과 활성 모델 내보내기를 마친 뒤 배포하는 것이 좋습니다. 지금 모델 없이 서버를 만들면 `/readyz`는 의도적으로 503입니다.

사용자는 코드, 검토 JSON, 환경 변수나 API URL 파일을 직접 편집할 필요가 없습니다. 비밀번호·토큰을 채팅으로 보내지 마세요. 계정 연결 후 발급된 공개 서버 주소만 전달하면 에이전트가 준비 상태 확인·사이트 연결·재배포를 진행합니다.

## 원문 검토 기록

[재점검 보고서](TRAINING_AUDIT.md)에 필수/선택 변수 구분과 원문 요청 목록을 정리했습니다. 전극 두께, 열처리 시간, 분위기, 정확한 wake-up 횟수는 일괄 필수에서 제외했습니다. 원문에 값이 없어도 자동으로 원본을 채우지 않으며, 실제 사용한 선택 값에는 원문 확인을 요구합니다. 전체 결측 열은 제외하고, 수치 보간·결측 표시자는 각 학습 fold에서만 학습합니다. 이 변경만으로 현재 승인 0행 문제가 해결되지는 않습니다.

```bash
cd /workspace/-
/workspace/hzo-venv/bin/python scripts/fetch_sources.py
```

다운로드 문서는 `artifacts/source_cache/<sha256>.txt`에 로컬로 보존합니다. 원문 전체는 Git에 공개하지 않습니다. 접속 성공·DOI 포함·문서 길이 검사는 접근 확인일 뿐 과학적 검증이나 승인이 아닙니다. 검토하는 에이전트가 논문 본문·Methods·Figure/Table을 읽어 수치, 단위, 전압 정의, 측정 방법과 상태, 소자 구조·조성·전극 전체 두께·삽입층·열처리를 대조해야 합니다. 근거가 없거나 Pr/2Pr/PUND 정의가 모호하면 승인하지 않습니다.

실제 판정은 `data/reviews/decisions.json`에 별도 기록합니다. 현재 판정 목록은 비어 있습니다. `src/reviews.py`는 다음을 검사합니다.

- 원본 기록 SHA256, 근거 문서 SHA256과 DOI 일치
- 인용 문장이 실제 원문 캐시에 존재하는지
- 레이블·측정 정의·필수 공정 조건의 명시적인 확인 항목
- 검토자·검토일·Figure/Table/Methods 위치와 범위 승인
- 승인 오버레이의 레이블 변경 금지; 검토 후 원본 변경 시 재검토 요구

이 검사는 근거 연결과 변조 탐지를 담당합니다. 인용문이 개별 수치를 과학적으로 뒷받침하는지 판단하는 원문 검토 자체를 자동화하거나 대체하지 않습니다.

Frontiers URL의 `/full`·`/pdf`를 DOI 일부로 읽던 문제를 수정했습니다. 같은 논문이 다른 DOI 그룹으로 갈라져 교차검증에 누출되지 않게 했으며, 이 수정 후 출처 간 중복 검토 후보는 14행입니다. 원본 기록을 임의 삭제하지 않습니다.

## 모델 학습과 내보내기

```bash
/workspace/hzo-venv/bin/python scripts/train_verified.py --method P-E
/workspace/hzo-venv/bin/python scripts/train_verified.py --method PUND
```

같은 측정 방법의 승인된 20관측치·5 DOI가 필요합니다. P-E와 PUND를 합쳐 이 기준을 넘기지 않습니다. DOI GroupKFold로 같은 논문·소자군의 관련 측정이 양쪽에 걸치지 않도록 하고, Random Forest와 Dummy 평균 기준의 MAE/RMSE/R²를 비교합니다. 기준 대비 MAE가 5% 이상 개선되고 R²가 양수일 때만 활성화합니다. 소수 논문 기반의 연구용 추정이며 인과·공정 보증이나 보정된 예측구간은 제공하지 않습니다.

실제 자료가 부족하면 종료 코드 2와 `artifacts/training_attempt.json`으로 차단 사유를 남깁니다. 검증이 실패하면 종료 코드 3입니다. 성공한 경우에만 `models/index.json`에 활성 버전, 모델·승인 데이터·검증 보고서·승인 기록의 해시를 등록합니다. 원본 파일 또는 판정이 바뀌면 기존 모델은 다시 학습하기 전까지 제공하지 않습니다. MFIS, Endurance, 열화 곡선은 별도 검증 모델이 생기기 전에는 제공하지 않습니다.

## 서버와 배포

`src/api.py`는 공개 읽기 전용 API이며 승인·업로드·학습·모델 파일 업로드 경로가 없습니다.

| 경로 | 의미 |
|---|---|
| `GET /healthz` | 서버 프로세스 실행 상태; 모델 준비와 별개 |
| `GET /readyz` | 검증 모델이 있어야 200, 없으면 503 |
| `GET /v1/models` | 실제 활성 모델, 버전·데이터 해시·검증 점수·입력 범위 |
| `POST /v1/predict` | 실제 모델 계산; 모델 없음 503, 범위/구조/정의 불일치 422/503, 버전 변경 409 |

```bash
/workspace/hzo-venv/bin/python -m pip install -r requirements-api.txt
/workspace/hzo-venv/bin/python -m uvicorn src.api:app --host 0.0.0.0 --port 8080
```

Render Blueprint는 `Dockerfile`로 이 서버를 시작하며 공개 사이트의 origin만 CORS에 허용합니다. 공개 inference 서버에서 검토 기능을 켜지 않습니다. Render 무료 서비스는 휴면·콜드 스타트와 자원 제한이 있으므로 상시 응답·SLA를 보장하지 않습니다. 호스팅 서비스가 변경되면 플랜 조건을 다시 확인해야 합니다.

로컬 컨테이너 검증:

```bash
docker build -t hzo-verified-inference .
```

관리형 네트워크의 신뢰 CA가 필요한 머신에서는 검증을 끄지 말고 빌드 시에만 신뢰 번들을 전달합니다. 공개 CA만 사용하는 Render/GitHub 빌드에서는 필요하지 않습니다.

```bash
docker build --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt -t hzo-verified-inference .
```

CA는 빌드 시크릿으로만 마운트하며 최종 이미지에 복사하지 않습니다. 컨테이너는 비특권 UID로 실행합니다. 모델이 없는 현재 이미지의 `/healthz` 200, `/readyz` 503, 활성 모델 0개를 로컬에서 확인했습니다.

실제 호스팅 주소가 발급되고 준비 검사를 통과한 다음 에이전트가 실행합니다.

```bash
/workspace/hzo-venv/bin/python scripts/configure_inference.py https://실제로-발급된-서버주소
```

위 주소는 설명용 자리표시자이며 실제 배포 주소가 아닙니다. 준비되지 않은 서버 주소는 설정에 저장하지 않습니다. 준비 검사를 통과하면 `docs/inference-config.json`이 갱신됩니다. 해당 파일을 GitHub에 반영하고 Pages를 재배포합니다. 현재 설정값은 null이며 가짜 서버 링크가 없습니다.

## 테스트 증거

- Python 테스트: 승인 근거·해시·정의 검증, API의 실제 모델 계산, 모델 부재, 입력 타입·범위, 구조·방법·대상 불일치, 버전/원본 변경, CORS와 편집 경로 부재를 검사합니다.
- `scripts/browser_smoke.py`: 기존 검색·정의 분리·모바일·Streamlit 기능을 검사합니다.
- `tests/browser_inference.py`: **임시 합성 자료로만** 학습한 모델을 별도 임시 HTTP 서버에서 실행합니다. 브라우저 입력이 Python 모델까지 전달되고, 입력 변경 시 다른 결과가 재계산되며, 이전 결과가 지워지고 범위 밖·MFIS 요청이 차단되는지 확인합니다. 테스트용 리버스 프록시만 사용하며 가짜 예측 응답으로 대체하지 않습니다. 테스트 모델·문서는 실행 종료 시 제거되며 저장소/공개 서버에 등록하지 않습니다.
- CI에 위 검사와 Docker 빌드·실행 검사를 포함했습니다. 이 테스트 통과는 연구 데이터의 원문 검증·모델 성능 통과 또는 공개 서버 배포 성공을 뜻하지 않습니다.
