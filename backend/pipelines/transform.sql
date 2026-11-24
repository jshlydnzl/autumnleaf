WITH normalized AS (
    SELECT row_no,
           trim(order_id, ' ' || chr(9) || chr(13) || chr(10)) AS order_id,
           trim(order_date, ' ' || chr(9) || chr(13) || chr(10)) AS supplied_date,
           trim(regexp_replace(trim(amount, ' ' || chr(9) || chr(13) || chr(10)), '^₱', ''),
                ' ' || chr(9) || chr(13) || chr(10)) AS supplied_amount
    FROM raw.orders
    WHERE run_id = $run_id
), parsed AS (
    SELECT row_no, order_id,
           count(*) OVER (PARTITION BY order_id) AS id_count,
           CASE WHEN regexp_full_match(supplied_date, $date_pattern)
                     AND substr(supplied_date, 1, 4) <> '0000'
                THEN try_cast(supplied_date AS DATE) END AS order_date,
           CASE WHEN regexp_full_match(supplied_amount, $amount_pattern)
                THEN try_cast(replace(supplied_amount, ',', '') AS DECIMAL(12, 2)) END AS amount
    FROM normalized
)
SELECT row_no, order_id, order_date, amount,
       CASE
           WHEN order_id = '' THEN 'Order ID is required.'
           WHEN id_count > 1 THEN 'Duplicate order ID.'
           WHEN order_date IS NULL THEN 'Use a valid date in YYYY-MM-DD format.'
           WHEN date_trunc('month', order_date) <> $month THEN 'Order date is outside the batch month.'
           WHEN amount IS NULL THEN 'Enter a non-negative amount with up to two decimal places.'
       END AS issue
FROM parsed
ORDER BY row_no
