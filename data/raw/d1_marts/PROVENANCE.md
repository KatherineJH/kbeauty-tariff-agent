# D1 선행 프로젝트 검증 마트 내보내기

수치 질문(S3·S4·S5)의 정답 원천이다. 파일 복사가 아니라 **출처 커밋에 고정된 재현 가능한 내보내기**다.

## 출처와 재현

- 선행 저장소: `kbeauty-us-supply-chain`, 커밋 `b3faac8044b7b67b8d32bbe6287b8e2798ca0b58`(2026-11-06, PR #1 병합). `SOURCE.md`가 자동 기록한다.
- 방법(`scripts/export_d1_marts.py`):
  1. 그 커밋을 `git archive`로 임시 폴더에 꺼낸다. 선행 저장소의 작업 트리는 쓰지 않는다.
  2. 선행 저장소 `data/SHA256SUMS`의 93개 파일 해시를 검증한다.
  3. 그 커밋의 `uv.lock`으로 `uv sync --frozen`, `dbt build`를 실행한다(70개 노드, 데이터 테스트 49개 모두 통과, DuckDB threads=1).
  4. 마트 9개를 `ORDER BY ALL`로 정렬해 Parquet(zstd)로 쓴다. 웨어하우스에서 계산한 논리 해시와 Parquet을 다시 읽어 계산한 논리 해시가 같아야 한다.
- 논리 해시: 열 이름·타입 머리줄 + 모든 열로 정렬한 행을 정규 직렬화(NULL은 `\N`, 실수는 최단 왕복 표현, 날짜는 ISO)한 SHA-256. `marts.csv`의 `logical_sha256`.
- 재실행 확인(2026-11-06): 두 번 내보낸 결과가 9개 마트 모두 논리 해시와 Parquet 바이트까지 같았다. Parquet 바이트 일치는 같은 환경에서 관찰된 것일 뿐 보장이 아니며, 기준은 논리 해시다.
- 타입 변환: Parquet에는 128비트 정수가 없어 `HUGEINT`(BIGINT 합계) 열을 `BIGINT`로 변환한다. 모든 값이 범위 안인지 먼저 확인한다. 변환한 열은 `schema.csv`의 `cast` 열에 적는다.
- 버전: 내보내기 쪽 duckdb 2.0.0(이 프로젝트 `uv.lock`), 빌드 쪽은 선행 저장소 `uv.lock`(duckdb 2.0.0, dbt-duckdb 1.11.1).

## 파일

| 파일 | 내용 |
|---|---|
| `<mart>.parquet` | 마트 9개: `dim_port`, `fct_imports_hs10_mode_monthly`, `mart_category_monthly`, `mart_country_panel_monthly`, `mart_mirror_monthly`, `mart_monthly_summary`, `mart_port_concentration_monthly`, `mart_port_region_monthly`, `mart_vessel_transit` (총 4,197행) |
| `marts.csv` | 마트별 행 수, 열 수, 정렬 기준(`ALL`), 논리 해시, Parquet 크기·해시 |
| `schema.csv` | 열 순서, 타입, NULL 허용, 변환, 선행 저장소 용어집의 설명과 단위 |
| `SOURCE.md` | 자동 생성 출처 기록(커밋, 해시 검증 수, dbt 결과, 내보내기 SQL) |

## 의미 (선행 저장소 정의를 그대로 따름)

- **날짜:** `month`는 해당 월 1일 날짜다. 미국 쪽 값은 Census 국제무역 API `imports/hs`의 `time`, 즉 **미국 수입 통계의 기록 월**이다. 수출 시점(선적일)이 아니다. 미국 쪽 범위는 2024-01~2026-08이다.
- **한국 쪽(`mart_mirror_monthly`의 `kr_*`):** 관세청 수출 통계의 수출 월이다. 범위는 2024-01~2026-09이고, 미국이 아직 공개하지 않은 달(16행)은 `us_*` 값이 NULL이다. 미국이 공개한 달에 값이 없는 HS6 줄은 0이다(선행 저장소 모델 주석).
- **금액:** USD. 미국은 일반 수입 금액 `GEN_VAL_MO`(과세가격, 운임·보험료 제외), 한국은 FOB다.
- **중량:** kg. Census는 해상·항공에만 중량을 공개한다. 그 밖의 운송수단 중량은 없다(`other` 금액 = 전체 − 해상 − 항공).
- **결측:** 선행 저장소 스테이징에서 해상·항공 금액·중량의 NULL을 0으로 바꾼다(`coalesce`). 마트 단위의 NULL 의미는 `schema.csv` 설명을 따른다.
