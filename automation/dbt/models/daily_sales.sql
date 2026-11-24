select order_date, count(*) as order_count, sum(amount) as revenue
from {{ ref('stg_orders') }}
group by order_date
