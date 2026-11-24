select row_no, order_id, order_date, amount
from {{ ref('checked_orders') }}
where issue is null
