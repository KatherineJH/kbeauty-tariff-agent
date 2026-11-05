# D2 미국 관세율표 (HTS)

- 기관: U.S. International Trade Commission, https://hts.usitc.gov/
- 수집: 2026-11-05, `pipeline/fetch_hts.py`. 요청 주소·시각·해시는 `manifest.csv`.
- 판: `RELEASE.txt` (수집 시 사이트 표시 2026 HTS Revision 22). 요청은 `release=currentRelease`이므로 재수집하면 다른 판이 내려올 수 있다. 분석은 이 폴더의 원문만 쓴다.
- 이용 조건: 미국 연방정부 저작물(17 U.S.C. §105). 사이트의 공식 Export·Download 기능만 사용. 출처: USITC, Harmonized Tariff Schedule of the United States.

| 파일 | 내용 |
|---|---|
| `export_ch33.json` | 33장(3301~3307) 세번·품명·세율(Export JSON) |
| `export_9903_01-02.json` | 99장 9903.01~9903.02 (IEEPA 추가 관세·국가별 상호관세 소호) |
| `export_9903_03.json` | 99장 9903.03 (122조 임시 수입 과징금 소호와 예외, 2026-11-05 추가) |
| `chapter_33.pdf`, `chapter_99.pdf` | 장 본문(주 포함). 99장 PDF는 약 14MB |
| `general_rules_of_interpretation.pdf` | 일반 해석 규칙(GRI) |
| `general_note_33.pdf` | 일반 주해 33(한-미 FTA) |
| `general_statistical_notes.pdf`, `change_record.pdf` | 통계 주해, 개정 기록 |

## 변경 기록

| 날짜 | 변경 | 이유 |
|---|---|---|
| 2026-11-05 | `export_9903_03.json` 추가, 폴더 전체 재수집 | 규정 효력 표 작성 중 122조 임시 수입 과징금(포고문 11012)의 HTS 소호가 9903.03에 있음을 확인. 재수집한 기존 8개 파일은 첫 수집과 SHA-256이 모두 같았다. 이는 **같은 날짜 재수집에서 관찰된 안정성**일 뿐 장기적인 재현성 보장이 아니다(`currentRelease`는 개정판이 나오면 바뀐다). 분석의 재현성은 이 폴더에 보관한 원문과 해시로 보장한다 |
