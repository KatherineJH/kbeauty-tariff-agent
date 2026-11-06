# 검색·관계·에이전트 확장 전략

이 문서는 현재 프로젝트의 검색 실패 분석을 바탕으로, 앞으로 비교할 검색 구성과 도입하지 않을 기술을 정한다. 기술 이름 자체를 목표로 삼지 않고, 같은 평가셋에서 정확도·비용·지연·재현성을 비교해 채택 여부를 결정한다.

이 문서는 **계획**이다. 구현된 것은 B1(BM25 기준선)과 그 평가(`run_001`~`run_003`)뿐이고, B2 이후 구성은 아직 없다. 현재 구조는 [architecture.md](architecture.md) 4.4, 평가 기준과 고정 qrel은 [evals/dev/README.md](../evals/dev/README.md), 실행 결과는 [reports/retrieval/README.md](../reports/retrieval/README.md)가 기준이며, 여기서는 수치와 규칙을 다시 적지 않는다.

## 1. 유지할 책임 경계

각 계층의 책임을 섞지 않는다.

| 계층 | 책임 | 구현 |
|---|---|---|
| 데이터·관계 | 규칙, 효력 기간, 개정·대체 관계, 증거 연결 | dbt + DuckDB |
| 계산 | 적용 규칙 선택과 모델링된 추가관세 계산 | 결정적 규칙 엔진 |
| 인용 | 주장별 공식 원문 검증 | `rule_citations`와 evidence catalog |
| 검색 | 관련 문서와 설명용 문맥의 후보 탐색 | BM25(구현). dense·hybrid·graph expansion은 계획 |
| 표현 | 구조화된 결과를 읽기 쉬운 답변으로 변환 | 현재는 결정적 조립(`answer/compose.py`). 생성 계층은 미구현 |

검색 결과는 규칙 엔진의 세율, 적용 기간, 해결 상태, 자동 계산 가능 여부와 검증된 인용을 덮어쓰지 않는다. 검색 결과가 없거나 서로 충돌해도 규칙 엔진의 결론을 임의로 변경하지 않고, 부족하거나 충돌한 근거를 별도 상태로 보고한다.

## 2. 현재 확인된 검색 실패

`run_003`(사용자 검수 qrel v2)에서 시점 불명확 질의 집합의 인용 6개 중 3개는 영어·한국어 모두 관련 청크가 하나도 없다(p09의 인용 2개, p10의 인용 1개). 순위를 바꿔도 찾을 수 없는 근거다. 원인은 검색 모델보다 청킹 과정에서 법률 문서의 계층 구조가 분리된 데 있다(탐색적 진단, 질의 수가 적다).

- p09: heading 청크에는 `9903.81.91`이 있지만 `3304.99.50`은 다음 청크에 있다.
- 코드 청크에는 `3304.99.50`이 있지만 어느 heading이나 note의 목록인지 없다.
- 같은 코드 목록이 철강, 알루미늄, 영국 대상 조항에 반복된다.
- p10: 제외 문장은 있으나 "그러한 추가 관세"가 가리키는 선행 문맥(과징금)이 잘려 있다.

따라서 텍스트가 검색되었다는 사실만으로는 관련성을 판정할 수 없다. 독립적인 검색 단위가 최소한 다음 문맥을 보존해야 한다.

- HTS 판본
- U.S. Note와 subdivision
- 적용 heading
- 관세 종류
- 국가·제품 범위
- 물리 페이지와 인쇄 페이지

## 3. 검색 구성과 실험 순서

순서는 B1 → B2(heading-enriched BM25) → DN1(dense) → H1(hybrid) → 필요할 때만 R1(reranker) → G1(graph expansion) → A1(제한된 agentic retry)이다. 기존 결과를 덮어쓰지 않고 각 구성을 별도 run으로 남기며, 새 run ID와 입력·코퍼스·청킹 해시를 기록한다.

비교 기준은 고정 qrel v2와 같은 관련성 기준이다. 다만 qrel은 청크 단위라서, 청킹을 바꾸는 구성(B2, G1)은 v2에 없는 새 청크를 만든다. 새 청크는 같은 기준으로 새로 판정해 새 qrel 버전으로 남기고 v2는 고치지 않는다. 비교 대상 구성은 같은 qrel 버전에서 다시 평가한다.

실험 ID `DN1`은 [data_sources.md](data_sources.md)의 원천 ID `D1`과 구분하려는 것이다.

### B1. 현재 BM25 (구현됨)

- 120단어 창, 30단어 overlap, k1 = 1.2, b = 0.75
- 결과: `run_001`~`run_003`
- 기존 기준선과 실패 사례를 그대로 보존
- 이후 구성의 개선폭을 판단하는 기준

### B2. Heading-enriched BM25 (미구현)

하위 청크에 상위 구조를 명시적으로 붙인다. 아래는 형식 예시이며 값은 실제 추출 결과로 정한다.

```text
Context:
HTS revision: 2025 Rev. 19
U.S. Note: 16(n)(3)
Applies to: 9903.81.91
Duty family: Section 232 steel derivative

Chunk:
3004.90.9244 ... 3304.99.50 ...
```

원문 텍스트와 추가한 구조 메타데이터를 구분하고, enrichment 규칙과 결과 해시를 기록한다. 구조 정보는 원문에서 결정적으로 추출하고 정답 인용(`rule_citations`)을 읽지 않는다. 현재 검수에서 `uncertain`으로 판정된 heading–code 분리 사례(p09, p10)가 독립 근거로 판정 가능해지는지, 도달 불가 인용 수가 줄어드는지를 우선 측정한다.

### DN1. Dense retrieval (미구현)

- 한국어 질문과 영어 문서의 교차언어 검색 개선 여부를 평가한다.
- 모델 ID, revision, tokenizer, pooling, normalization, 입력 prefix를 고정한다.
- 정확한 HTS 코드, 날짜, 부정 표현에서 발생하는 실패를 별도로 보고한다.

### H1. Hybrid retrieval (미구현)

- BM25와 dense 결과를 결합한다.
- 결합 방식과 파라미터를 dev에서만 정한다.
- exact match와 의미 검색이 서로 보완되는지 평가한다.

### R1. Reranker (미구현, 필요할 때만)

- 상위 후보의 정밀도 개선이 필요한 경우에만 추가한다.
- 검색 지표 개선뿐 아니라 지연 p50/p95와 비용을 함께 측정한다.
- 개선이 작거나 유의하지 않으면 더 단순하고 빠른 구성을 선택한다.

### G1. Parent-child 또는 graph expansion (미구현)

작은 청크로 검색한 뒤 명시적 관계를 따라 필요한 상위 문맥을 붙인다.

```text
chunk
  -> belongs_to -> U.S. Note/subdivision
  -> applies_to -> tariff heading
  -> implements -> regulatory action
  -> valid_during -> revision interval
  -> supported_by -> evidence
```

우선 DuckDB의 관계 테이블과 재귀 쿼리로 구현한다. Neo4j 없이도 효과를 검증할 수 있어야 한다.

### A1. 제한된 agentic retry (미구현)

고정 검색 구성을 평가한 뒤, 검색 실패 복구가 필요한 경우에만 추가한다.

```text
질문
-> 1차 검색
-> 근거 충분성 검사
-> 부족하면 HTS·EO 식별자 추출 또는 질의 재작성
-> dense/hybrid 검색이나 구조 확장 1회
-> 검증된 evidence와 대조
-> 답변 또는 모름
```

최대 단계 수, 허용 도구, 재시도 횟수와 종료 조건을 고정한다. 모든 질의, 도구 호출, 결과와 상태 전이를 record/replay 대상으로 기록한다.

## 4. 관계 모델

현재 dbt seed와 모델이 도메인 관계의 일부를 이미 관계형 테이블로 갖고 있다. 검색 단위와 이어지는 관계는 아직 없다.

| 관계 | 상태 | 위치 |
|---|---|---|
| rule segment -> derived from -> regulatory action | 있음 | `rule_segments.action_id` |
| rule segment -> applies to -> HTS scope | 있음 | `rule_segments.hts_scope`, `rule_hts_lists` |
| regulatory action -> amends/supersedes -> regulatory action | 있음 | `regulatory_actions`의 `amends`·`supersedes`·`superseded_by`, `int_action_relations` |
| rule segment -> valid during -> period | 있음 | `rule_segments`의 `starts_at`·`ends_at` |
| claim -> supported by -> evidence | 있음 | `rule_citations` |
| evidence -> found in -> revision/page | 있음 | `rule_citations`의 파일·쪽, `evidence_catalog` |
| chunk -> belongs to -> note/subdivision | 없음 | B2·G1에서 추가 |
| note/subdivision -> applies to -> tariff heading | 없음 | B2·G1에서 추가 |

Knowledge Graph는 데이터 모델이고 Neo4j는 가능한 저장·조회 구현 중 하나다. 다음 조건이 생기기 전에는 별도 그래프 DB를 도입하지 않는다.

- 관계 종류와 규모가 크게 증가한다.
- 다단계 traversal이 빈번해 SQL이 실질적으로 복잡해진다.
- 그래프 탐색·시각화 UI가 필요하다.
- 벤치마크에서 그래프 DB의 이점이 확인된다.

## 5. 답변 상태와 사용자 표시

빠른 답변과 최종 답변을 구분하더라도 검증 전 관세 금액을 잠정적으로 표시하지 않는다. 규칙 엔진에 구현된 상태는 `computed_modelled_only`·`incomplete`·`refused_uncertain`이다. `preliminary`·`verified`는 검색·답변 흐름을 위한 제안 상태이며 아직 구현하지 않았다.

| 상태 | 의미 | 표시 원칙 |
|---|---|---|
| `preliminary` (제안) | 관련 규정 후보를 찾았으나 검증 전 | 후보 확인 중임을 표시하고 금액은 숨김 |
| `verified` (제안) | 규칙 엔진과 주장별 인용 검증 완료 | 모델링 범위와 근거를 함께 표시 |
| `computed_modelled_only` | 모델링한 추가관세만 계산 완료 | 총관세가 아님을 명시 |
| `incomplete` | 입력이나 근거가 부족함 | 필요한 입력과 미해결 요소 표시 |
| `refused_uncertain` | 날짜·판본·범위가 불명확함 | 계산을 거부한 이유 표시 |

## 6. 평가 기준

검색 구성마다 다음을 같은 평가셋에서 보고한다.

### 검색 품질 (구현됨, 정의는 `src/tariffagent/retrieval/evaluate.py`)

- Recall@5/10(macro·micro), MRR@10, nDCG@10, 결과 0건 비율
- 도달 불가 인용 수(관련 청크가 하나도 없는 인용)
- 영어·한국어 결과, 그리고 조건이 같은 질의쌍만 쓴 paired 비교와 언어 격차
- 답 가능 질의(시점 불명확 질의는 따로)와 답 불가 질의(빈 결과 비율)

### 최종 과제 (미구현)

- 규칙·도구 선택 정확도
- 최종 과제 성공률
- 인용 정밀도·재현율
- 과잉 거절률과 근거 없는 확정 비율
- 첫 검색 성공률과 재검색 후 성공률

### 운영 비용 (미구현)

- 지연 p50/p95
- 질문당 토큰·비용
- 검색·도구 호출 수
- 평균·최대 검색 단계 수
- 재검색으로 정답을 잃은 비율

성공률 차이가 유의하지 않으면 더 단순하고 빠르고 싼 구성을 선택한다.

## 7. 재현성과 변경 관리

- 코퍼스, 청킹 규칙, 검색 설정과 qrel의 해시를 기록한다.
- 동일 입력의 청크 ID와 검색 순서를 결정적으로 만든다.
- dev에서만 파라미터를 조정하고 기존 run을 수정하지 않는다.
- test 셋(아직 없음)을 만든 뒤에는, 그 결과를 본 다음 구성이나 qrel을 덮어쓰지 않는다.
- 영어·한국어 질의쌍은 조건까지 동일한 경우에만 paired 비교에 포함한다.
- 검색 결과는 검증된 답변 인용과 분리한다.
- 실호출 에이전트(아직 없음)는 record/replay로 재채점 가능하게 한다.

## 8. 현재 적용 순서

1. 사람 보조 qrel 검수와 `run_003`을 확정한다. **완료**(커밋 `c1426c9`).
2. B2 heading-enriched BM25를 구현하고 B1과 비교한다. 다음 단계이며 아직 시작하지 않았다.
3. DN1 dense retrieval을 평가한다.
4. H1 hybrid retrieval을 평가한다.
5. 필요할 경우 R1 reranker를 평가한다.
6. G1 parent-child 또는 graph expansion을 평가한다.
7. A1 제한된 agentic retry를 평가한다.

## 9. 현재 보류

다음 항목은 현재 보류한다. 핵심 구성의 효과를 확인하기 전에는 도입하지 않는다.

- Neo4j 또는 별도 Knowledge Graph 데이터베이스
- LangGraph
- 외부 Vector DB(dense 실험은 로컬 파일 색인으로 시작한다)
- 무제한 반복 에이전트
- 검색 결과가 규칙 엔진의 결론을 수정하는 구조
- 검증 전 잠정 관세 금액 표시
- 모든 원천을 하나의 인덱스에 강제로 통합
- 증분 인덱싱과 자동 파일 작업

LangGraph는 검색 분기, 병렬 실행, 사람 승인, 중단·재개와 체크포인트 요구가 복잡해진 뒤 비교 구성으로 검토한다. 증분 인덱싱은 실서비스 전환 시 새 HTS 판본만 처리할 필요가 생겼을 때 추가한다.

## 10. 핵심 가설

아직 검증하지 않은 가설이다. B2·G1의 결과로 확인한다.

이 프로젝트의 검색 실패는 검색 모델의 능력 부족만이 아니라 법률 문서의 계층 구조가 청킹 과정에서 분리되는 데서 발생한다. 상위 heading·note·관세 종류·판본 문맥을 청크에 보존하거나 관계를 따라 확장하면, 코드 목록의 의미를 독립적으로 판정할 수 있어 검색 관련성과 최종 답변의 근거성이 개선될 것이다.
