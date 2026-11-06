{#- Source time text -> TIMESTAMPTZ.
    'YYYY-MM-DD'                 -> 00:00 in var('local_tz') (precision 'date': time of day unknown)
    'YYYY-MM-DDTHH:MM+/-HH:MM'   -> that instant (the source text, with its UTC offset, is kept in *_source)
    '' or NULL                   -> NULL -#}
{% macro parse_ts(col) -%}
case
    when {{ col }} is null or trim({{ col }}) = '' then null
    when length(trim({{ col }})) = 10 then (cast(trim({{ col }}) as timestamp) at time zone '{{ var("local_tz") }}')
    else cast(trim({{ col }}) as timestamptz)
end
{%- endmacro %}

{% macro ts_precision(col) -%}
case
    when {{ col }} is null or trim({{ col }}) = '' then null
    when length(trim({{ col }})) = 10 then 'date'
    else 'minute'
end
{%- endmacro %}
