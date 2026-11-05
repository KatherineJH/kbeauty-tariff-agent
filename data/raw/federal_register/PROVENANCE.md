# D4 미국 관보 (Federal Register)

- 기관: Office of the Federal Register, REST API https://www.federalregister.gov/api/v1 (API 키 없음)
- 수집: 2026-11-05, `pipeline/fetch_federal_register.py`. 요청 주소·시각·해시는 `manifest.csv`.
- 선정: `pipeline/fr_documents.csv` 20건(상호관세 7, 임시 수입 과징금 1, 소액면세 7, IEEPA 환급 1, 301조 4). 선정 규칙은 수집 스크립트 머리말에 있고, 선정에 쓴 검색 응답 4개(`search_*.json`)를 그대로 보관한다.
- 파일: 문서마다 API 레코드 `doc_<번호>.json`과 본문 `doc_<번호>.html`(`raw_text_url`이 내려주는 GPO HTML, 본문은 `<pre>` 블록).
- 이용 조건: API 문서의 유일한 제한은 재게시 시 NARA·OFR 로고·인장 사용 금지. FederalRegister.gov 본문은 법적 효력본이 아니며 공식본은 GPO(govinfo) 판이다. 인용 시 FR 문서 번호와 게재일을 함께 적는다.

## 변경 기록

| 날짜 | 변경 | 이유 |
|---|---|---|
| 2026-11-05 | 포고문 11012(2026-03824, 임시 수입 과징금) 추가, 검색 1개 추가, 선정 규칙 (a)를 "상호관세 **또는 그 밖의 추가 관세**"로 넓힘. 폴더 전체를 다시 수집 | 첫 수집 19건의 본문(EO 14389 2(c))을 읽은 뒤, 영향받지 않는 조치로 이 포고문이 이름으로 특정된 것을 발견했다. 처음 검색어(reciprocal tariff, de minimis, Korea reciprocal)로는 잡히지 않았다. **본문을 읽은 뒤 규칙을 넓힌 것**이므로 기록으로 남긴다. 평가셋 작성 전이라 평가에는 영향이 없다 |
