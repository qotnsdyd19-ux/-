# HZO Version 2 검증 보고서

기준 Version 1: `678b3337f9cd8c17cb9672983bdb950af43d40e9`. `version2` 브랜치에서 개발하며 기존 이력과 원본 워크북을 보존합니다.

| 항목 | 결과 |
|---|---|
| 기존 출처 기록 | 112행 (49 + 63), 확인 시트 10행 중복 합산 제외 |
| 추가 Excel | 152행; 10개 시트 검사; 통합 시트와 7개 분류 시트의 ID·전체 셀 일치 검사 |
| 추가 CSV | 37행; 원본 모든 열 보존; DOI·Figure 위치는 없으므로 추측하지 않음 |
| 통합 출처 기록 | 301행; **독립 실험 수가 아님** |
| 구조 정확히 MFM | 221행 (기존 100 + 신규 Excel 96 + CSV 25) |
| 구조 정확히 MFIS | 35행 (신규 Excel); MFIS_FTJ 1행은 별도 |
| 기타 구조 | 45행; MFS, MFIM, FTJ, 산화층/기판접촉 변형, 미확인을 MFM/MFIS에 강제 편입하지 않음 |
| 2Pr 점값 후보 | 204행; 원문 승인과 별개; Pr·충돌·하한은 제외 |
| 출처 간 중복 검토 후보 | DOI 정규화 수정 후 14행; 같은 DOI·2Pr·두께·열처리 온도. 독립성 확인 전 학습 제외, 원본은 모두 보존 |
| 승인 관측치 / 독립 DOI | 0 / 0 |
| MFM 모델 | 기존 Random Forest, DOI GroupKFold, Dummy 기준 비교, 모델 버전·범위 차단 유지 |
| MFM 학습 / 교차검증 | 실제 자료의 train 호출은 승인 게이트에서 차단; CV 미실행; 합성 fixture에서만 모델 학습·추론·범위 및 버전 차단 테스트 |
| MFIS 모델 | 미구현/미검증. 독립 화면·데이터 경계 구현, MFM 모델 유입 차단 |
| 2Pr / Endurance | 미검증. 시험종료·고장·피로 시작·하한·검열 관계를 원문대로 별도 보존 |
| Memory Window / ΔVth | 확인된 수치 레이블 0행; 예측 없음 |
| MAE / RMSE / R² | 실제 연구 모델은 N/A |
| 2Pr–Cycles 곡선·조건 추천 | 미구현. 반복 상태 관측치를 가상 곡선으로 보간하지 않음 |
| 실제 공개 예측 주소 | 없음. Pages는 후보 탐색 화면이며 Python 추론 서버가 아님 |

`docs/model_status.json`은 구조·타깃별 숫자 후보 수와 차단 상태, `docs/review_queue.csv`는 각 기록의 검토·제외 사유입니다. `data/normalized.csv`는 원본 JSON·시트·행·DOI·전극 문자열·측정 및 cycling 조건을 보존합니다. 분류 시트는 `sheet_membership`으로 연결합니다. 같은 소자군의 전계·반복 횟수가 다른 측정은 별도로 유지합니다.

CSV의 `twoPr` 열은 **파일 작성자가 표기한 후보**입니다. Pr 배증 여부, P–V/P–E/PUND 정의, 전압의 ±V/Vpp/|V|, 펄스폭 단위와 실제 프로토콜을 원문에서 재확인해야 합니다. Excel의 PRIMARY, REPORTED, ML 후보 표시는 승인 근거로 자동 사용하지 않습니다. 이번 작업에서는 원문 논문의 전체 프로토콜과 수치를 독립 대조하지 않았으므로 새 승인 기록을 생성하지 않았습니다.

JavaScript: 작업 시작 시 현재 main의 스크립트는 Node 구문 검사를 통과했습니다. 따라서 보고된 `Illegal return statement`를 해당 커밋에서 재현했다고 주장하지 않습니다. 긴 인라인 코드를 `docs/site.js` 모듈로 분리하고 실제 Chromium 실행, 페이지 오류 수집, `node --check`를 회귀 검사에 추가했습니다.

## 실행 및 검증

Python 3.12에서:

```bash
python3 -m venv /workspace/hzo-venv
/workspace/hzo-venv/bin/python -m pip install --no-cache-dir -r requirements-dev.txt
/workspace/hzo-venv/bin/python -m pytest -q
/workspace/hzo-venv/bin/python scripts/build_site.py
git diff --exit-code -- data docs
```

앱은 읽기 전용 기본값을 유지합니다. 공개 사이트에서 업로드·승인·재학습을 활성화하지 않습니다.

```bash
HZO_READ_ONLY=1 /workspace/hzo-venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
/workspace/hzo-venv/bin/python -m http.server 8000 --bind 127.0.0.1 --directory docs
# 별도 셸에서; 시스템 chromium 또는 Playwright 설치 브라우저 필요
/workspace/hzo-venv/bin/python scripts/browser_smoke.py
```

회귀 검사는 기존 워크북 파싱·승인 위조 차단·DOI 분리·실제 모델 추론·범위/버전 차단을 유지하고, 신규 시트 중복 검사·정의 격리·구조 격리·브라우저 다운로드/업로드/메모·모바일 화면을 추가합니다. CI는 정적 생성물 일치와 브라우저 검증까지 수행합니다.

## 배포 및 남은 조건

후속 작업에서 FastAPI 추론 API, Docker 이미지, Render 배포 설정과 사이트 호출 경로를 구현했습니다. [배포 및 원문 검증 절차](DEPLOYMENT.md)를 참고하세요. 원문 접근과 계정 연결이 완료되지 않아 실제 연구 모델과 공개 추론 주소는 아직 없습니다.

GitHub Pages는 기존 Actions 워크플로로 `docs/`를 배포합니다. 정적 탐색에는 추가 Python 서버 비용이 없습니다. 기존 설정과 플랜에 따른 Pages 제공 조건은 GitHub 정책을 따릅니다.

공개 추론에는 Python 호스팅이 별도로 필요합니다. 기존 Streamlit 앱을 읽기 전용으로 Streamlit Community Cloud 등에 배포할 수 있으나, 이번에는 승인 데이터·활성 모델·실제 배포 URL이 없으므로 가짜 백엔드 링크를 넣지 않았습니다. Community Cloud의 무료 범위·휴면·자원 제한이 있으며 모델 및 리뷰는 영구 저장·백업 설계가 필요합니다. 유료 호스팅 비용은 선택 서비스에 따라 다릅니다. 공개 추론과 비공개 승인/학습을 같은 무인증 편집 서버로 운영하지 않습니다.

필요한 추가 자료: DOI와 원문 Figure/Table/Methods, 독립 소자군 식별자, 전극 전체/삽입층 두께, 조성·열처리 시간·분위기, 측정 방법·전압 정의·펄스폭·주파수·상태/반복 횟수. MFM은 현재 승인 기준인 최소 20 관측치·5 DOI부터 검증합니다. MFIS는 Memory Window/ΔVth 정의와 수치가 필요하며, Endurance는 고장 기준 및 시험 종료/검열 정보를 포함해야 합니다. 이후에만 별도 모델 설계·그룹 검증·기준 모델 비교·추론 서버 배포를 진행할 수 있습니다.
