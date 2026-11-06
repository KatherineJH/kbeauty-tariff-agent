# D2a 과거 HTS 판본 (USITC 아카이브)

- 기관: U.S. International Trade Commission, 아카이브 https://hts.usitc.gov/download/archive
- 수집: 2026-11-06, `pipeline/fetch_hts_archive.py`. 판본별 폴더의 `manifest.csv`에 요청 주소·시각·SHA-256.
- 선정 규칙: `docs/data_sources.md`의 D2a 절. 다운로드 전에 로컬 문서에 작성했으나 커밋하지 않았으므로, 수집 결과와 같은 커밋으로 함께 기록된다(사전 고정의 커밋 증빙 없음). 미해결 효력 경계의 직전·직후 판본 12개만 받았다. `revisions.csv`에 판본, 아카이브 게시일, 링크의 `releaseDate`, 경계를 적었다.
- 파일: 판본마다 `chapter_99.pdf`(약 14~16MB)와 `change_record.pdf`. **PDF는 git에 커밋하지 않는다**(manifest의 URL·크기·SHA-256만 커밋). 다시 받기: `uv run python scripts/rehydrate_hts_archive.py`.
- 이용 조건: D2와 같다(미국 연방정부 저작물, 공식 다운로드만 사용).
- 아카이브 안내문: 중간 전자 개정판은 모두 보존되지 않는다. 그래서 판본 사이에 변화가 없었다고 추론하지 않는다. 효력일은 change record에 적힌 날짜만 쓰고, 날짜 근거가 없는 경계는 `archive_gap`으로 표시한다.
- change record가 근거로 든 관보 문서: 대부분 번호 없이 "Executive Order", "Notice", "PP 11012", "PP 11021"로만 적혀 있다. 번호로 특정되지 않은 문서는 이번에 수집하지 않았다.
