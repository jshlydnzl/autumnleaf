with normalized as (
    select row_no,
           trim(order_id, ' ' || chr(9) || chr(13) || chr(10)) as order_id,
           trim(order_date, ' ' || chr(9) || chr(13) || chr(10)) as supplied_date,
           trim(regexp_replace(trim(amount, ' ' || chr(9) || chr(13) || chr(10)), '^₱', ''),
                ' ' || chr(9) || chr(13) || chr(10)) as supplied_amount
    from {{ source('raw', 'orders') }}
), parsed as (
    select row_no, order_id,
           count(*) over (partition by order_id) as id_count,
           case when regexp_full_match(supplied_date, '{{ var("date_pattern") }}')
                and substr(supplied_date, 1, 4) <> '0000'
                then try_cast(supplied_date as date) end as order_date,
           case when regexp_full_match(supplied_amount, '{{ var("amount_pattern") }}')
                then try_cast(replace(supplied_amount, ',', '') as decimal(12, 2)) end as amount
    from normalized
)
select row_no, order_id, order_date, amount,
       case
           when order_id = '' then 'Order ID is required.'
           when id_count > 1 then 'Duplicate order ID.'
           when order_date is null then 'Use a valid date in YYYY-MM-DD format.'
           when date_trunc('month', order_date) <> date '{{ var("batch_month") }}'
                then 'Order date is outside the batch month.'
           when amount is null then 'Enter a non-negative amount with up to two decimal places.'
       end as issue
from parsed
