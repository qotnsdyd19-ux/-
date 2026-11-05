# HZO Ferroelectric AI Predictor

Hf₀.₅Zr₀.₅O₂ MFM 강유전체의 공정 조건과 문헌 2Pr를 탐색하고, **원문 검토를 승인한 데이터만으로** Python Random Forest를 학습하는 연구 앱입니다. Endurance 및 MFIS 예측은 포함하지 않습니다.

- **GitHub Pages (`docs/`)**: 반응형 다크 테마, 연속 수치 입력 화면, 문헌 검색·필터, 2Pr 산점도, 원문 링크, CSV 및 품질 리포트 다운로드. Python 실행·업로드·학습 기능은 없습니다.
- **Streamlit (`app.py`)**: 위 기능 + Excel/CSV 업로드, 검토·승인/제외, 검토 이력 보존, DOI 분리 교차검증, 모델/데이터 버전 저장, 학습 범위를 검사하는 예측.
- **현재 모델 없음**: 초기 자료에는 학습을 승인한 기록이 없습니다. 예측 버튼은 비활성화되고 결과는 `—`, 성능·예측구간은 `N/A`로 표시됩니다. 숫자를 만들어 보여주지 않습니다.

## 실행

Python 3.11 이상 (검증 환경: Python 3.12).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

기본은 **읽기 전용**입니다. 본인만 접근할 수 있는 연구 환경에서 검토·업로드·재학습을 사용하려면:

```bash
HZO_READ_ONLY=0 streamlit run app.py
```

앱 자체에 로그인·권한 분리 기능은 없습니다. 공개 서버에서는 읽기 전용을 유지하세요. 공동 편집은 인증된 배포와 별도 권한 관리 구현 후 사용해야 합니다. `artifacts/`는 Git에서 제외되며, SQLite 리뷰/감사 로그 및 모델 버전이 여기에 저장됩니다. 임시 호스팅에서는 재배포 시 사라질 수 있으므로 영구 볼륨과 백업을 사용하세요. `joblib` 모델은 앱이 생성한 로컬 파일만 사용하며 외부 모델 업로드를 받지 않습니다.

## GitHub Pages 게시

저장소 **Settings → Pages → Build and deployment → Source: GitHub Actions**를 선택합니다. `Deploy HZO explorer to Pages` 워크플로를 실행하면 `docs/`를 배포합니다. 저장소가 비공개인 경우 계정 플랜에 따라 Pages 사용이 제한될 수 있습니다.

Pages 예상 주소: `https://qotnsdyd19-ux.github.io/-/` (Pages 활성화 및 배포 성공 후 사용 가능). 정적 호스팅에서는 Python 모델을 실행할 수 없으므로 연구 관리 앱은 별도 Streamlit 서버에서 실행해야 합니다. Streamlit Community Cloud 사용 시 이 저장소, `main`, `app.py`를 선택하고 읽기 전용으로 배포하세요. 실제 배포 주소는 해당 서비스에서 발급받습니다.

정적 화면 로컬 확인:

```bash
python -m http.server 8000 --directory docs
```

## 실제 첨부 데이터 해석

개발 지시 PDF에 명시된 파일명과 실제 첨부파일은 다릅니다. 실제 두 파일을 모두 사용했고, PDF의 40+10 중복 규칙은 해당 워크북에 적용했습니다.

| 파일/시트 | 원본 행 | 처리 |
|---|---:|---|
| `HZO_데이터2.xlsx` / 데이터 | 63 | 전체 보존. 숫자 2Pr 후보 38행. Endurance 측정 블록은 원본 JSON에 보존하며 학습 특징으로 사용하지 않음 |
| `HZO_MFM 20 논문의 데이터값..xlsx` / 01_2Pr_40행 | 40 | 2Pr 후보 40행 |
| 동일 파일 / 02_수치원문확인_10행 | 10 | Sample ID+DOI로 본 시트와 대조, 추가하지 않음. 수치 확인 표기를 승인으로 취급하지 않음 |
| 동일 파일 / 04_2Pr아닌자료_9행 | 9 | Pr·정의 불명확 레이블을 별도로 보존. two_pr는 결측 유지 |

결과: **112행 보존 / 숫자 2Pr 후보 78행 / 원문 학습 승인 0행**. 두 워크북의 P01 등 논문ID는 다른 논문을 뜻할 수 있어 합치지 않습니다. 논문 목록을 단순 합산해 고유 논문 수라고 표시하지 않습니다. DOI는 소문자로 정규화하되 없는 DOI를 추측하지 않습니다. 데이터2의 링크는 Excel hyperlink target에서 읽습니다. 제목이 ‘RTA’인 열도 각 행의 처리 방식을 확정하지 않으므로 데이터2의 `anneal_type`은 원문 검토 전 결측으로 둡니다.

`source_file`, `source_sheet`, `source_row`, `record_id`, `raw_json`, DOI, 원문 URL, Figure/Table, 검증 표기와 비고를 보존합니다. 숫자로 해석할 수 없는 범위·문자열은 평균이나 중앙값으로 바꾸지 않습니다. 원본에 이미 들어 있는 추출·중앙값 후보는 원본과 비고를 그대로 보존하며 승인 없이 학습하지 않습니다. Pr를 두 배로 바꾸지 않습니다. 열의 순서 대신 헤더를 매핑하며, 데이터2에서 반복되는 측정 헤더는 2Pr와 Endurance 블록을 분리합니다.

원본 재변환 / 정적 화면 데이터 갱신:

```bash
python -m src.data
python scripts/build_site.py
```

생성물: `data/normalized.csv`, `data/quality.json`, `data/papers.json`, `docs/data.json` 등. 정적 화면은 번들된 원본만 사용하며 로컬 승인 이력이나 모델은 공개하지 않습니다. 새 자료를 공개하려면 원본을 검토한 뒤 `data/raw/`에 추가하고 재생성·커밋하세요.

## 업로드 → 검토 → 승인 → 재학습

1. 개인 환경에서 편집 모드로 실행합니다. 두 HZO 워크북 형식 또는 정규화 CSV를 업로드합니다. 파싱 결과를 확인한 뒤 **미승인 후보로 추가**합니다. 업로드 파일의 승인 필드는 받아들이지 않습니다.
2. 각 기록의 원문·Methods·Figure/Table을 직접 대조합니다. 전극 전체 두께와 삽입층 두께, 측정 전압, P-E/PUND, wake-up 상태·횟수, 열처리 방식, 조성을 확인합니다. 근거가 없으면 승인하지 않습니다.
3. 원본을 덮어쓰지 않는 검토 오버레이에 확인한 값을 입력하고 검토자·근거를 남깁니다. 단층 다결정, 삽입층 없는 단일 금속 전극 MFM, Hf:Zr 1:1, RTA 범위를 확인한 기록만 승인할 수 있습니다. 제외/검토중 판정도 저장합니다. 레이블 숫자 변경은 지원하지 않으며 정정된 레이블은 새 원본 기록으로 제출해야 합니다.
4. 승인 후에도 필수 결측, 비RTA, 비2Pr, 다층/삽입층, 중복 의심 기록은 학습에서 제외됩니다. 파일 간 DOI·2Pr·두께·전극·온도·전압이 같은 기록은 가능한 중복으로 표시하고 보수적으로 제외합니다. 서로 다른 관측치가 이 조건을 공유할 수도 있으므로 원문 검토 및 별도의 식별 기준 보강이 필요합니다.
5. **20개 이상 관측치 / 5개 이상 독립 DOI**일 때 재학습합니다. 이 수는 초기 운영 제한일 뿐 통계적 신뢰성을 보장하지 않습니다. 자료가 적으면 UI를 이용한 검색·품질 점검만 가능합니다.

CSV 최소 열: `sample_id,metric,two_pr,doi,source_locator`. 나머지 필드는 `data/normalized.csv`를 템플릿으로 사용하세요. 필수 학습 조건은 `src/model.py:REQUIRED`에 정의되어 있습니다. 전압만 있는 입력을 지원하며, 전기장만 있는 원본은 전압을 자동 환산하지 않으므로 검토 시 해당 측정 조건에 대한 전압 확인이 필요합니다.

## ML 및 검증 한계

`ColumnTransformer` + `SimpleImputer` + `OneHotEncoder(handle_unknown="ignore")` + `RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42, n_jobs=2)`.

- 각 DOI는 같은 fold에만 속합니다. 5분할 GroupKFold의 out-of-fold 결과로 MAE/RMSE/R²를 계산하고 DummyRegressor(mean)와 비교합니다. 보간기는 각 학습 fold 안에서만 학습합니다.
- 필수 공정·측정 변수는 검토 후 완비해야 합니다. ALD 온도·펄스폭·주파수 등 선택 수치만 파이프라인에서 보간할 수 있으며 원본 CSV에는 반영하지 않습니다. 전체 결측 선택 변수는 파이프라인 내부에서만 처리됩니다.
- RF의 OOF MAE가 기준 모델보다 낮을 때만 활성화합니다. 실패한 버전도 보고서와 함께 보존합니다. 이 비교는 소수 논문·선택 편향·하이퍼파라미터 불확실성을 해결하지 않습니다.
- 숫자 학습 범위를 벗어난 값, 알려지지 않은 범주/전극 조합, 다층 조건은 예측을 차단합니다. 개별 변수 범위 안의 새 조합이 물리적으로 유효하다고 보장하지 않습니다.
- 보정된 불확실성 구간이 없어 95% 신뢰구간은 표시하지 않습니다. 계산할 수 없는 R²는 N/A입니다.
- 데이터·승인 내역의 해시가 바뀌면 기존 모델로 예측하지 않습니다. `artifacts/models/<version>/`에 모델, 승인 데이터 스냅샷, 검증 보고서를 저장하여 이전 버전을 보존합니다.
- PDF 자동 수치 추출은 후속 단계입니다. 자동 추출값도 원문 승인 없이 학습하지 않는 동일한 수집·검토 경로를 사용해야 합니다.

## 테스트

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

실제 첨부파일 행 수와 확인 시트 중복 제거, Pr 분리, RTA/MWA 구분, 업로드 승인 위조 차단, DOI 누출 방지, 모델 부재/학습 범위 밖/데이터 버전 변경 시 예측 차단, 모델 버전 저장, 원본 보존 및 Streamlit 화면 실행을 검증합니다. ML 테스트의 합성 데이터는 테스트 내부에서만 생성하며 연구 데이터나 실제 모델로 배포하지 않습니다.

## 구성

```text
app.py                  Streamlit 연구 UI
src/data.py             헤더 매핑, 원본 보존, 정규화/품질
src/model.py            승인 게이트, DOI CV, 버전 관리, OOD
src/store.py            로컬 SQLite 리뷰/감사 이력
scripts/build_site.py   공개 탐색 화면 데이터 재생성
 data/raw/              사용자 제공 원본 Excel
 data/                  정규화 및 품질 리포트
 docs/                  GitHub Pages 정적 사이트
 tests/                 데이터/모델/UI 회귀 검증
```
