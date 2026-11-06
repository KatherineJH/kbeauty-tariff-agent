# 아키텍처와 재현성 정의

작성 2026-11-05. 시스템 범위, 데이터 모델, 재현성의 정의를 적는다. 평가의 가설·판정 규칙은 [`preregistration.md`](preregistration.md), 데이터 원천은 [`data_sources.md`](data_sources.md)에 있다.

## 1. 문제와 범위

미국에 화장품을 수출하는 K-뷰티 브랜드 담당자는 2025~2026년의 관세·통관 규정 변화 속에서 다음을 묻는다.

- 이 물건은 **어느 날짜 기준으로** 어떤 관세·통관 규정을 적용받는가
- 우리 품목의 세번과 세율은 무엇인가
- 정책 전후 시장(수입 금액·중량·단가)은 어떻게 움직였나

답은 영문 규정 문서(날짜별로 효력이 바뀜)와 통계(미국 기록과 한국 기록이 서로 다름)에 흩어져 있다.
이 프로젝트는 **규정 RAG + 통계 SQL + 독립 검증**으로 답하고, 그 성능을 사전 등록한 기준으로 평가한다.

범위 밖: CBP 판정례(CROSS, 자동 취득 경로 없음), 법률 자문, 실시간 규정 추적.

## 2. 질문 유형

| 유형 | 예시 | 필요한 것 |
|---|---|---|
| S1 품목·세율 | "3304.99 화장품의 일반 세율과 한-미 FTA 특혜 세율은?" | HTS 검색, 인용 |
| S2 날짜별 규정 | "2025-08-20 / 2026-03-10에 수입 신고한 한국산 화장품에 상호관세가 붙나?" | 규정 효력 모델(4절) |
| S3 시장 수치 | "정책 후 12개월 스킨케어 항공 수입 금액 변화는?" | SQL(선행 프로젝트 마트) |
| S4 출처 대조 | "정책 후 K-뷰티가 더 싸졌나?" | 미국·한국 기록 모두 조회, 모순 보고 |
| S5 조건부 결정 | "서부 하역을 유지해야 하나? 근거와 가정은?" | SQL + 규정 + 선행 프로젝트 의사결정 표 |
| S6 답할 수 없음·주입 | 자료에 없는 질문, 문서에 심은 지시문 | 거절, 지시 무시 |

## 3. 구성

```
data/raw (원문·해시) ─ verify ─▶ pipeline/ --offline ─▶ data/extracted/ (본문 텍스트, 청크, 규정 효력 표)
                                                          ▼
                                warehouse/ (dbt + DuckDB): 문서·청크·규정 효력·정답 마트 + 데이터 테스트
                                                          ▼
src/tariffagent/
  retrieval/  BM25 · 밀집(정확 검색) · 하이브리드(RRF) · 재순위
  llm/        공급자 추상화 + 기록·재생(record/replay) + 토큰·비용·지연 기록
  agents/     LangGraph: 감독자 ─┬─ 규정 에이전트(HTS·관보 RAG + 효력 표 조회)
                                ├─ 통계 에이전트(SQL, 읽기 전용)
                                └─▶ 검증 에이전트(초안을 보지 않고 수치·인용·효력 일자 재확인)
  eval/       채점기(검색·생성·에이전트), 통계 검정, 실패 분류
  serve/      FastAPI 비동기 /ask, /health (평가와 같은 answer() 경로)
reports/      표·그림·시스템 카드·실패 기록(추가만)
```

멀티 에이전트를 두는 구조적 이유:
1. **독립 검증** — 답을 만든 에이전트가 스스로 검증하면 자기 결론을 지지하는 근거만 찾는다.
2. **권한 분리** — DB 읽기 권한은 통계 에이전트만 가진다. 문서에 심은 지시문이 SQL 도구에 닿지 않는다.
3. **문맥 분리** — 긴 규정 본문과 SQL 결과를 한 문맥에 섞지 않는다(효과는 측정 대상).

성능상 필요한지는 단일 에이전트·단순 RAG와 같은 평가셋으로 비교해 판정한다. 이기지 못하면 그대로 보고한다.

## 4. 규정 효력 데이터 모델

날짜별 질문(S2)은 "게재일 전/후"처럼 날짜 하나로 나눌 수 없다. 서명·게재·효력·징수 종료가 서로 다르고, 한 문서가 일부 조치만 종료하기 때문이다.
예: EO 14389(서명 2026-02-20, 관보 게재 2026-02-25)는 IEEPA에 근거한 추가 종가관세(EO 14257 상호관세 등)를 효력 상실시키고 "가능한 한 신속히" 징수를 끝내라고 명한다(2(a)). 232조·301조 관세에는 영향이 없다고 명시한다(2(d)).
EO 14389 본문은 EO 번호를 직접 표기하지 않고, 2026-02-20자 「Continuing the Suspension of Duty-Free De Minimis Treatment for All Countries」와 같은 날짜의 임시 수입 과징금 포고문(「Imposing a Temporary Import Surcharge to Address Fundamental International Payments Problems」)을 제목과 날짜로 특정하여 영향받지 않는다고 명시한다(2(c)). Federal Register API 메타데이터(`disposition_notes`, `executive_order_notes`)는 이를 각각 EO 14388, Proc. 11012로 식별한다.

`warehouse/seeds/regulatory_actions.csv`(사람이 원문을 읽고 작성, 각 값에 근거 위치 기록):

> **현재 상태(2026-11-06): 초안.** 이 표는 완성된 관세 계산표가 아니다. 17행 모두 출처 문장과 대조했다(`evidence_status = quote_checked`). 해결 상태는 13행 `resolved`, 4행 `partial`이다(`resolution_status`).
> 다만 작성자 대조일 뿐 사용자 검수 전이며, 일부 행은 `open_issues`에 단서(caveat)를 남긴다. 앞으로 확정할 수 없는 값이
> 생기면 `incomplete`로 두고 추정해 채우지 않는다. 자료 공백(`archive_gap`)은 평가에서 단일 정답 대신 "공식 자료만으로
> 확정할 수 있는가"를 묻는 불확실성 처리 질문으로 쓴다.

| 열 | 뜻 |
|---|---|
| `action_id` | 조치 식별자(예: `EO14257_reciprocal`) |
| `instrument` | 근거 문서(EO 번호, FR 문서 번호) |
| `legal_basis` | IEEPA, 232조, 301조, 19 U.S.C. 1321 등 |
| `signed_at` | 서명일 |
| `published_at` | 관보 게재일 |
| `effective_at` | 효력 발생 시점(시각·시간대 포함 가능) |
| `ends_at` | 효력 종료 시점(미정이면 비움, `ends_rule`에 서술) |
| `applicability_rule` | 기준 사건: 수입 신고일(entered for consumption), 창고 반출일, 선적일 등 + 예외(운송 중 화물 특례 등) |
| `scope` | 대상 국가·품목·운송 경로 |
| `rate_or_effect` | 세율 또는 효과(면세 중단 등) |
| `supersedes` / `superseded_by` | 대체 관계 |
| `amends` | 수정 관계 |
| `unaffected_actions` | 이 문서가 명시적으로 영향을 주지 않는다고 한 조치 |
| `source_quote_ref` | 근거 문장의 문서·문단 위치 |
| `rate_kind`, `rate_pct` | `additional_ad_valorem`(기본세율에 더함) / `total_with_column1`(기본세율과 합쳐 `rate_pct`가 되도록, 기본세율이 그 이상이면 0) / `none`. 예: 301조 한국 12.5%는 **합산 총 12.5%**이지 추가 12.5%가 아니다 |
| `stacking_rule` | 다른 추가 관세·232조·MFN과의 중첩 규칙(원문 인용) |
| `archive_evidence` | 날짜를 뒷받침하는 과거 HTS 판본·쪽·change record 항목, 또는 `archive_gap` |
| `cosmetics_3303_3307` | 화장품 소호(3303~3307)에 대한 예외 판정과 근거 쪽. 표현은 "검토한 HTS Rev. 22 기준으로 예외로 확인되지 않음"처럼 한정한다 |
| `evidence_status` | `quote_checked`(작성자가 채운 값을 모두 원문 문장과 대조함, 사용자 검수 전) / `unverified` |
| `resolution_status` | `resolved` / `partial`(인용은 확인했지만 적용 모델링·시각이 일부 남음, 예: 철강·알루미늄 동시 함유 수입 건) / `unresolved`(필요한 값이 코퍼스에 없음) |
| `open_issues` | 원문에서 확정할 수 없는 값과 그 이유. 값을 추정해 채우지 않는다 |

표는 `scripts/_build_regulatory_actions_seed.py`의 행 정의에서 생성한다(값 안의 쉼표를 안전하게 인용하기 위해).

**쪽 번호 규칙:** `pdf_page`와 인용의 "PDF p."는 `data/raw/hts/chapter_99.pdf`의 물리 쪽(1부터)이다. 인쇄된 쪽 표기(예: `99-III-486`)는 `printed_page` 열이나 괄호 안에 함께 적는다.

**시점 규칙:** HTS 예외 판정의 기본은 Rev. 22(2026-11-05 현행)다(`data/extracted/cosmetics_exception_check.csv`). 과거 시점은 경계 전후 판본(D2a, 12개)과 그 change record의 효력일로 판정하고, 효력 표의 `archive_evidence` 열에 근거 판본과 쪽을 적는다. 날짜 근거가 없는 경계는 `archive_gap`으로 표시하고 `incomplete`로 남긴다. 판본 사이에 변화가 없었다고 추론하지 않는다.

dbt 테스트(예): 모든 `instrument`가 수집된 원문에 존재, `signed_at ≤ published_at`, 대체 관계에 순환 없음, `effective_at`이 비면 `ends_rule`처럼 서술 근거가 있음.
에이전트는 효력 판단을 이 표의 조회로 하고, 본문 RAG는 근거 인용에 쓴다. 이 분리 자체를 평가한다(효력 표 없이 RAG만 쓴 구성과 비교).

### 4.1 웨어하우스 계층 (dbt, `warehouse/`)

| 계층 | 모델 | 역할 |
|---|---|---|
| seed | `regulatory_actions` | 출처 기록(인용, 증거, 상태). 사람이 원문을 읽고 작성 |
| seed | `rule_segments`, `rule_code_resolution`, `rule_hts_lists`, `list_versions`, `duty_families`, `action_evidence`, `evidence_catalog` | 계산용 재진술(`scripts/_build_rule_seeds.py`) |
| seed | `boundary_fixtures`, `family_fixtures` | **사람이 작성한 정적 기대값.** 생성 코드와 분리(`warehouse/seeds/README.md`) |
| staging | `stg_regulatory_actions`, `stg_rule_segments`, `stg_hts_exception_codes` | 명시적 타입. 시각은 `TIMESTAMPTZ`, 원문 시각 문자열은 `*_source`에 보존 |
| intermediate | `int_action_relations`, `int_regulatory_action_periods`, `int_fixture_rule_states` | 선언된 관계, 구간과 경계 불확실 구간, fixture 기준 적용 상태 |
| mart | `mart_tariff_rules`, `mart_rule_code_resolution`, `mart_tariff_rule_lists` | 규칙 엔진 입력 |

- **구간:** 모든 기간은 반개구간 `[effective_at, ends_at)`이다. `ends_at`이 NULL이면 코퍼스에 종료가 없다는 뜻이다. `rate_pct`가 NULL이면 세율이 아니다(`rate_kind = none`).
- **날짜만 아는 경계:** 원문이 날짜만 주는 경계(`precision = date`)는 효력 시각이 아니다. `effective_at`/`ends_at`의 그날 00:00 America/New_York 값은 정렬용이고, 그날 하루 전체(`effective_at`~`start_uncertain_until`, `ends_at`~`end_uncertain_until`)를 **불확실**로 둔다. 이 구간에서는 자동 계산하지 않는다. 날짜는 `effective_on`/`ends_on`에 따로 둔다.
- **해결 상태의 단위:** action이 아니라 규칙 구간(`resolution_status`)이 기본 단위다. HTS 코드 단위로 덮어쓸 수 있다(`mart_rule_code_resolution`). 예를 들어 과징금 구간 A는 232 금속이 없는 화장품 10개 소호에는 `resolved`, 232 파생품 14개 소호에는 `partial`이다. 자동 계산은 해당 코드의 해결 상태가 `resolved`이고 시각이 불확실 구간 밖일 때만 한다.
- **목록의 시점:** 모든 HTS 목록에 `source_revision`, `valid_from`, `valid_to`, `temporal_status`가 있다. Rev. 22에서 읽은 예외 목록(3,775개 코드)은 `current_revision_only`이며 `valid_from` = 2026-10-30(Rev. 22 게시일)이다. 그보다 이른 시점에는 목록 소속을 판정할 수 없어 **불확실**이 된다. 예외적으로 그 기간 판본에서 코드 단위로 확인한 경우(`list_membership_verified`, 화장품 24개 소호)만 판정한다.
- **관세 종류:** 각 규칙은 `duty_family`(`ieepa_reciprocal`, `s232_derivative`, `s122_surcharge`, `s301`, `de_minimis`)에 속한다. MFN은 `not_modelled`다. "2026-02-24 00:00에 과징금 없음"을 "아무 관세도 없음"으로 읽지 않도록 관세 종류별 fixture를 둔다.
- **범위:** 원산지는 한국만 모델링한다(소액면세는 `ALL`). HTS 목록 비교는 8단위 소호 또는 10단위 줄의 정확 일치만 쓴다. 232 파생품 목록은 33장 화장품만 담는다.
- **책임 경계:** dbt는 관세 총액을 계산하지 않는다. 한 시점에 적용·불확실인 규칙 집합을 결정적으로 돌려주는 데까지만 맡는다. 중첩과 가액 구성 계산은 규칙 엔진이 한다.
- **데이터 테스트(48개):**
  - 상태 허용값
  - 관계 ID·증거 ID 참조 무결성
  - 반개구간
  - NULL 의미
  - 비해결 행·구간·코드의 사유 필수
  - 목록 범위 코드 존재
  - 미선언 중첩 실패
  - 현행 목록의 과거 사용 금지
  - 경계값 fixture 57개(적용·불확실·자동 계산의 세 집합)
  - 관세 종류별 fixture 31개
- **negative test(pytest, 5건):** 다음과 같이 seed를 훼손하면 지정한 dbt 테스트가 반드시 실패해야 한다.
  - 경계 기대값을 틀리게 바꿈
  - 232 알루미늄·철강 관계를 제거함
  - 한-미 합의의 대체 관계를 제거함
  - 현행 목록의 유효 시작일을 과거로 당김
  - 관세 종류별 기대값을 틀리게 바꿈

### 4.2 규칙 엔진 (`src/tariffagent/rules/engine.py`)

- **두 단계뿐이다.**
  - `select_rules`: 마트 필드만으로 규칙마다 `applies` / `uncertain` / `not_applicable`과 그 사유를 정한다. 법령 해석을 새로 하지 않으며, dbt 기준 모델(`int_fixture_rule_states`)과 모든 fixture에서 판정이 같아야 한다(테스트).
  - `evaluate`: 계산을 허용한 적용 규칙의 추가 관세를 `Decimal`로 계산한다. 반올림 규칙은 모델링하지 않았으므로 원시 `Decimal`을 그대로 둔다.
- **입력(`EntryInput`):**
  - 필드: `entry_at`(시간대 필수), `origin_country`, `hts_code`(`NNNN.NN.NN` 또는 `NNNN.NN.NNNN`만), `customs_value_usd`, `transport_mode`, `is_postal`, `steel_content_value_usd`, `aluminum_content_value_usd`, `components_are_disjoint`, `column1_rate_pct`(`total_with_column1` 규칙에만 필요)
  - 다음은 거부한다: `float`, 음수, 금속 함량 합계가 과세가격을 넘는 경우, 지원하지 않는 HTS 형식, 시간대 없는 시각.
  - 시각은 UTC 순간으로 비교한다. 여름(EDT, UTC−4)과 겨울(EST, UTC−5) 경계를 테스트로 고정했다.
- **자동 계산 허용:** `resolved`만 계산한다. `partial` 규칙은 계산하지 않고 `incomplete`로 돌려준다. 다만 코드별 해결 조건(`resolved_when`)을 입력이 충족하면 그 수입 건에 한해 `resolved`로 본다.
  - 예: 과징금 구간 A는 232 파생품 소호의 과세 기준을 "가액 − 232 금속 함량"으로 정한다. 엔진은 철강·알루미늄 가액이 서로 겹치는지 알 수 없다. 그래서 두 가액이 모두 입력되고 `components_are_disjoint = True`가 선언될 때만 계산한다.
  - 232 파생품 두 구간은 경계일 밖에서 `resolved`다. 경계일의 시각 미상은 불확실 구간으로 처리했고, Notice 미식별은 증거에 대한 단서다.
- **계산 순서:**
  1. 232 파생품의 금속 함량
  2. 상호관세, 122조 과징금, 301조
  3. 소액면세 중단은 효과만 기록한다.
- **가액 구성:** 금속 함량이 필요한데 입력이 없으면 전체 가액으로 대신하지 않는다.
- **세율 종류:**
  - `additional_ad_valorem`: 가액 × 세율
  - `total_with_column1`: 가액 × max(세율 − column 1 세율, 0). 0으로 바닥 처리하는 근거는 두 원문이 column 1이 상한 이상이면 추가 세율이 0이라고 명시하기 때문이다(FR 2025-21940, 2026-15181). 근거 문장 자체를 테스트한다.
- **상태:** `status`와 함께 `coverage = modelled_families_only`, `not_modelled_families = ["mfn"]`을 항상 돌려준다.

  | 상태 | 뜻 |
  |---|---|
  | `computed_modelled_only` | 모델링된 관세 종류의 적용 규칙을 모두 계산함. MFN 등 미모델링 관세에 대해서는 아무것도 말하지 않는다 |
  | `incomplete` | 입력 부족이나 `partial` 규칙 때문에 합계를 내지 않음 |
  | `refused_uncertain` | 날짜만 아는 경계일이거나 목록 소속을 확인할 수 없어 계산을 거부함. 필요한 정보를 함께 적음 |

- **출력:** `computed_duties[]`(계산 순서, 가액, 적용 세율, 금액, 증거), `modelled_additional_duty`, `unresolved_components[]`(`not_modelled` / `uncertain` / `missing_input` / `partial_rule`, 필요한 입력 포함), `applied_rule_ids[]`, `excluded_rule_ids[]`(상태·사유), `evidence_ids[]`, `trace[]`.
- **결정성:** 출력 순서는 마트의 행 순서와 무관하다. 관세 종류 순서와 `rule_id`로 정렬한다.

### 4.3 주장 단위 인용 답변 (`src/tariffagent/answer/`, 검색 이전의 기준선)

엔진 결과 → 규칙 ID → 주장(권한·세율·시작·종료·범위·예외·중첩·해결 조건) → 주장 역할별로 검증된 원문 발췌 → 구조화 답변. LLM과 검색은 아직 쓰지 않는다.

- **명시적 인용 seed(`warehouse/seeds/rule_citations.csv`, 74개):**
  - 사람이 작성한다. 규칙 구간마다 `claim_role`(`authority`, `rate`, `effective_start`, `effective_end`, `scope`, `exclusion`, `stacking`, `resolution_condition`)별로 `evidence_id`, `source_file`, `physical_page`, `printed_page`, 인용 문장을 적는다.
  - 자동 탐색(`scripts/_draft_rule_citations.py`)은 후보 파일·쪽을 나열하는 초안 도구일 뿐이다. 같은 문장이 여러 쪽에 있으면(예: 2025 Rev. 19의 화장품 목록 문장이 주 16(n)·16(u)·19(k)·19(s)의 네 쪽에 있음) 사람이 쪽을 골라 seed에 고정한다.
- **검증(`load_verified`):**
  - 인용 문장이 **지정한 파일에** 있는지, 물리 쪽이 파일명과 맞는지, 인쇄 쪽이 그 쪽의 표기와 맞는지, 파일이 `evidence_id`에 속하는지, 파일 바이트가 잠금 파일(`data/extracted/rule_citations.lock.csv`)과 같은지만 확인한다.
  - 다른 파일이나 쪽으로 넘어가 찾지 않는다. 하나라도 어긋나면 즉시 `CitationError`.
  - seed를 고친 뒤에는 `scripts/lock_rule_citations.py`로 검증하고 잠금을 다시 쓴다.
- **커버리지(`check_coverage`):**
  - 구간의 필드가 요구하는 역할마다 인용이 있어야 한다.
    - 항상: 권한, 시작, 범위
    - 세율이 있으면: 세율
    - 종료가 있으면: 종료
    - 예외 목록 범위면: 예외
    - 금속 함량 가액 구성이나 `total_with_column1`이면: 중첩
    - 코드별 해결 조건이 있으면: 해결 조건
  - 구간의 기간을 만든 모든 조치(`rule_segments.period_actions`)에서 시작·종료 인용이 하나 이상 있어야 한다. 예: 한국 10% 구간 B는 EO 14266(중지), EO 14316(연장), EO 14326 2(e)(계속)를 모두 인용해야 한다.
  - 하나의 문서가 여러 역할을 충족해도 된다.
- **답변(`compose`):**
  - 문장(statement)마다 주장 목록(`claims`)을 두고, 각 주장에 같은 역할의 citation ID를 연결한다. 그 역할의 인용이 없으면 조립이 실패한다.
  - 해결 조건으로 계산한 금액에는 `resolution_condition` 주장이 붙는다. 예: 과징금 구간 A의 금속 파생품 소호에는 주 2(aa)(v)(b)·(d)의 금속 함량 제외 문장과 비금속 부분 부과 문장이 붙는다.
  - 상태와 금액은 엔진 그대로다. `computed_modelled_only`는 "This is not the total duty."로 쓰고, `incomplete`·`refused_uncertain`은 금액을 쓰지 않는다.
  - 검색 문맥은 `background`에만 들어간다.
- **알려진 한계:** 232 파생품의 권한 인용은 실제 적용 조문인 HTS 주의 문장이다. 그 바탕의 포고문은 코퍼스에 없다.

다음 단계: 이 기준선에 BM25·dense·hybrid 검색을 차례로 붙여 비교한다.

## 5. 재현성 정의

| 대상 | 기준 | 비교 방법 |
|---|---|---|
| 원문(`data/raw`), LLM 기록, 평가셋, 프롬프트 | 바이트 | SHA-256 |
| 재추출 표(본문 텍스트, 청크, 효력 표) | **정규화된 논리 내용** | 키로 정렬, 열 순서 고정, 텍스트 정규화(유니코드 NFC, 줄바꿈 LF, 앞뒤 공백) 후 해시. Parquet 파일 바이트는 비교하지 않음 |
| 임베딩 | 커밋된 벡터 | 해시. 재계산할 때는 코사인 허용 오차 |
| 평가 지표(재생 모드) | 정확 일치 | 외부 호출 0회, 표 정확 비교 |
| 평가 지표(실호출) | 분포 | 반복 실행의 평균·범위를 진단값으로 보고(보장 아님) |

- 재생 모드: LLM 호출 키 = SHA-256(모델, 파라미터, 메시지, 도구 정의). 캐시 미스는 실패.
- CI(Linux, 비밀값 없음): 해시 검증 → 오프라인 재추출 → dbt build·테스트 → 재생 모드 평가 → 표 비교·품질 회귀 게이트 → Docker 스모크.
- 재현성의 범위는 세 단계로 나뉜다.
  1. **커밋된 증거 → 평가표:** 오프라인 재현 가능. 테스트와 `scripts/rehydrate_hts_archive.py --check`가 증거 스냅샷, 쪽 해시, 논리 해시의 일관성을 검사한다.
  2. **공식 PDF → 증거 추출:** 네트워크 재수집이 필요하다. 받은 PDF가 manifest의 SHA-256과 같아야 추출하고, 추출 결과는 논리 해시와 같아야 한다(`scripts/rehydrate_hts_archive.py`).
  3. **원본 PDF의 장기 가용성:** USITC 아카이브에 의존한다. 원본이 사라지면 2단계는 재현할 수 없고, 1단계만 남는다.
- 정정은 기존 기록을 고치지 않고 행을 추가한다(사전 등록 변경 기록, 실패 기록, 검수 기록).

## 6. LLM과 비용

- OpenAI API의 저비용 모델 1개, 테스트 용도로만 사용. 모델 ID와 가격표 날짜를 설정 파일에 고정.
- 실호출은 dev 반복과 test 평가에만 쓰고, 나머지는 기록 재생.
- 키는 `.env`에만 둔다.
