-- Code-level exception lists of HTS Revision 22 chapter 99 (built by pipeline/extract_hts_exceptions.py).
-- regime 'surcharge' = U.S. note 2(aa), 's301_korea' = U.S. note 52; codes are 8-digit subheadings or 10-digit lines.
select
    regime                       as list_id,
    subdivision,
    exempting_heading,
    code,
    cast(digits as integer)      as digits,
    cast(pdf_page as integer)    as pdf_page,
    printed_page
from read_csv('{{ var("extracted_dir") }}/hts_exception_codes.csv', header = true,
              types = {'code': 'VARCHAR', 'digits': 'VARCHAR', 'pdf_page': 'VARCHAR'})
where regime in ('surcharge', 's301_korea')
