select row_no, issue
from {{ ref('checked_orders') }}
where issue is not null
