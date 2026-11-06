# 관세 변화 대응 K-뷰티 수출 의사결정 에이전트

> 상태: **원천·D1 고정, 규정 효력 dbt 계층, 결정적 규칙 엔진, 구조화 인용 답변(검색 이전 기준선).** 구조와 재현성 정의는 [`docs/architecture.md`](docs/architecture.md), 원천과 이용 조건은 [`docs/data_sources.md`](docs/data_sources.md).

2025년 8월 상호관세와 소액면세 중단 이후, 미국에 수출하는 K-뷰티 브랜드 담당자의 질문
("우리 제품 세번이 맞나, 언제부터 관세가 얼마인가, 시장은 어떻게 움직였나")에
**규정 문서 RAG + 수입통계 SQL + 독립 검증 에이전트**로 답하고, 그 성능을 **데이터를 보기 전에 정한 기준**으로 평가한다.

선행 프로젝트 `kbeauty-us-supply-chain`의 검증된 데이터 마트를 수치 정답의 원천으로 쓰고, 같은 체계를 따른다.

| 장치 | 이 프로젝트에서 |
|---|---|
| 원문 SHA-256 대조, 오프라인 재추출 | 원문은 바이트 해시. 재추출한 청크는 **정규화된 논리 내용 해시** 일치(행 정렬·열 순서·텍스트 정규화 후 해시. Parquet 등 파일 바이트는 라이브러리 버전에 따라 달라질 수 있어 비교하지 않음). 임베딩·평가셋·프롬프트·LLM 기록도 해시 |
| dbt 데이터 테스트 | 청크·정답 마트 테스트(정답 SQL 재실행 일치, qrel 무결성) |
| 사전 등록 | 가설·지표·판정 규칙을 시스템 실행 전에 커밋, 정정은 행 추가로만 |
| 고정 | test 셋 commit-reveal, 시점 홀드아웃 |
| Linux CI | API 키 없이 기록 재생(replay) 모드로 전체 평가 |

## 구조 (예정)

```
data/raw        원천 응답 원문(해시)        pipeline/   수집·오프라인 재추출
data/extracted  정제 텍스트·청크             warehouse/  dbt + DuckDB
data/replay     LLM 호출 기록(재생용)        src/tariffagent/  retrieval · llm · agents · eval · serve
evals/          평가셋(dev 공개, test 봉인)   reports/    표·그림·시스템 카드
docs/           설계, 사전 등록, 검수 기록
```

## 실행

```bash
uv sync --frozen
uv run python scripts/build_warehouse.py      # 규칙 seed 재생성 → dbt build(데이터 테스트 48개)
uv run python scripts/lock_rule_citations.py  # 인용 seed 검증(지정 위치만)·필수 역할 커버리지·파일 해시 잠금
uv run pytest -q -m "not slow"                # 개발용(약 1분): 무결성·재현성·경계값·증거·규칙 엔진
uv run pytest -q                              # 전체 검증(CI): 위 + negative test(slow, 약 8분)
uv run python scripts/rehydrate_hts_archive.py --check   # 과거 HTS 증거 스냅샷 오프라인 검사
```
