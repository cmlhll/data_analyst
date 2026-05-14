# 数据库：销售数据集 (Sales Dataset)

## 1. sales_customers (客户信息表)
- 描述：记录客户的基本信息和分群
- 字段：
  - customer_id (PK, string): 客户唯一标识
  - name (string): 客户姓名
  - city (string): 客户所在城市
  - age (int): 客户年龄
  - segment (string): 客户分群 (Consumer/Corporate)

## 2. sales_products (产品信息表)
- 描述：记录产品和品类信息
- 字段：
  - product_id (PK, string): 产品唯一标识
  - product_name (string): 产品名称
  - category (string): 产品品类
  - price (float): 产品单价

## 3. sales_orders (订单明细表)
- 描述：记录每笔订单的详细信息
- 字段：
  - order_id (PK, string): 订单唯一标识
  - product_id (FK -> sales_products.product_id): 产品ID
  - customer_id (FK -> sales_customers.customer_id): 客户ID
  - quantity (int): 购买数量
  - order_date (datetime): 订单日期
  - revenue (float): 订单金额