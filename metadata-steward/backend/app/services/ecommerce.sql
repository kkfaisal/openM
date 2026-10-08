-- Ecommerce schema for the OpenMetadata source PostgreSQL database.
-- Some tables/columns are intentionally left WITHOUT comments so the
-- steward has real documentation gaps to detect.

-- ---------------------------------------------------------------- customers
CREATE TABLE IF NOT EXISTS customers (
  customer_id   SERIAL PRIMARY KEY,
  first_name    VARCHAR(100) NOT NULL,
  last_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(255) NOT NULL UNIQUE,
  phone         VARCHAR(30),
  address_line1 VARCHAR(255),
  city          VARCHAR(100),
  country       VARCHAR(100),
  postal_code   VARCHAR(20),
  created_at    TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE  customers IS 'Registered customers of the ecommerce store.';
COMMENT ON COLUMN customers.customer_id IS 'Unique customer identifier.';
COMMENT ON COLUMN customers.first_name   IS 'Customer first name.';
COMMENT ON COLUMN customers.last_name    IS 'Customer last name.';
COMMENT ON COLUMN customers.email        IS 'Customer email address (unique).';
COMMENT ON COLUMN customers.created_at   IS 'Timestamp the customer record was created.';

-- ---------------------------------------------------------------- categories
CREATE TABLE IF NOT EXISTS categories (
  category_id SERIAL PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  description TEXT
);

COMMENT ON TABLE  categories IS 'Product categories used for catalog organisation.';
COMMENT ON COLUMN categories.category_id IS 'Unique category identifier.';
COMMENT ON COLUMN categories.name        IS 'Category display name.';

-- ---------------------------------------------------------------- products
CREATE TABLE IF NOT EXISTS products (
  product_id     SERIAL PRIMARY KEY,
  category_id    INTEGER REFERENCES categories(category_id),
  sku            VARCHAR(64) NOT NULL UNIQUE,
  name           VARCHAR(200) NOT NULL,
  description    TEXT,
  price          NUMERIC(10,2) NOT NULL,
  currency       VARCHAR(3) DEFAULT 'USD',
  stock_quantity INTEGER NOT NULL DEFAULT 0,
  is_active      BOOLEAN DEFAULT true,
  created_at     TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE  products IS 'Products available for sale in the storefront.';
COMMENT ON COLUMN products.product_id IS 'Unique product identifier.';
COMMENT ON COLUMN products.sku        IS 'Stock keeping unit (SKU) code.';
COMMENT ON COLUMN products.name       IS 'Product display name.';
COMMENT ON COLUMN products.price      IS 'Unit price in the configured currency.';

-- ---------------------------------------------------------------- orders
CREATE TABLE IF NOT EXISTS orders (
  order_id         SERIAL PRIMARY KEY,
  customer_id      INTEGER NOT NULL REFERENCES customers(customer_id),
  order_date       TIMESTAMP NOT NULL DEFAULT now(),
  status           VARCHAR(30) NOT NULL DEFAULT 'pending',
  subtotal         NUMERIC(12,2) NOT NULL,
  tax              NUMERIC(12,2) NOT NULL DEFAULT 0,
  shipping         NUMERIC(12,2) NOT NULL DEFAULT 0,
  total_amount     NUMERIC(12,2) NOT NULL,
  shipping_address TEXT,
  created_at       TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE  orders IS 'Customer orders placed in the store.';
COMMENT ON COLUMN orders.order_id   IS 'Unique order identifier.';
COMMENT ON COLUMN orders.customer_id IS 'Customer that placed the order.';
COMMENT ON COLUMN orders.status     IS 'Order lifecycle status.';

-- ---------------------------------------------------------------- order_items
CREATE TABLE IF NOT EXISTS order_items (
  order_item_id SERIAL PRIMARY KEY,
  order_id      INTEGER NOT NULL REFERENCES orders(order_id),
  product_id    INTEGER NOT NULL REFERENCES products(product_id),
  quantity      INTEGER NOT NULL,
  unit_price    NUMERIC(10,2) NOT NULL,
  discount      NUMERIC(10,2) DEFAULT 0
);

COMMENT ON TABLE  order_items IS 'Line items that belong to an order.';
COMMENT ON COLUMN order_items.order_item_id IS 'Unique line item identifier.';

-- ---------------------------------------------------------------- payments
-- Intentionally left undocumented (table + columns) to create a gap.
CREATE TABLE IF NOT EXISTS payments (
  payment_id     SERIAL PRIMARY KEY,
  order_id       INTEGER NOT NULL REFERENCES orders(order_id),
  payment_method VARCHAR(30) NOT NULL,
  amount         NUMERIC(12,2) NOT NULL,
  currency       VARCHAR(3) DEFAULT 'USD',
  card_number    VARCHAR(20),
  status         VARCHAR(30) NOT NULL DEFAULT 'completed',
  paid_at        TIMESTAMP DEFAULT now()
);

-- ---------------------------------------------------------------- inventory
-- Intentionally left undocumented to create a gap.
CREATE TABLE IF NOT EXISTS inventory (
  inventory_id     SERIAL PRIMARY KEY,
  product_id       INTEGER NOT NULL REFERENCES products(product_id),
  warehouse_code   VARCHAR(20) NOT NULL,
  quantity_on_hand INTEGER NOT NULL DEFAULT 0,
  reorder_level    INTEGER DEFAULT 0,
  updated_at       TIMESTAMP DEFAULT now()
);

-- ---------------------------------------------------------------- reviews
-- Intentionally left undocumented to create a gap.
CREATE TABLE IF NOT EXISTS reviews (
  review_id   SERIAL PRIMARY KEY,
  product_id  INTEGER NOT NULL REFERENCES products(product_id),
  customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  rating      INTEGER NOT NULL,
  comment     TEXT,
  created_at  TIMESTAMP DEFAULT now()
);

-- ---------------------------------------------------------------- seed data
INSERT INTO customers (first_name, last_name, email, phone, address_line1, city, country, postal_code) VALUES
('Alice',  'Johnson', 'alice@example.com', '+1-555-0101', '123 Main St',   'Austin',   'USA', '78701'),
('Bob',    'Smith',   'bob@example.com',   '+1-555-0102', '456 Oak Ave',   'Denver',   'USA', '80202'),
('Carol',  'Davis',   'carol@example.com', '+1-555-0103', '789 Pine Rd',   'Seattle',  'USA', '98101'),
('Dan',    'Wilson',  'dan@example.com',   '+1-555-0104', '321 Elm St',    'Portland', 'USA', '97201'),
('Eve',    'Brown',   'eve@example.com',   '+1-555-0105', '654 Maple Dr',  'Boston',   'USA', '02108');

INSERT INTO categories (name, description) VALUES
('Electronics', 'Consumer electronics and gadgets'),
('Apparel', 'Clothing and accessories'),
('Home & Kitchen', 'Home goods and kitchenware'),
('Books', 'Books and media');

INSERT INTO products (category_id, sku, name, description, price, stock_quantity) VALUES
(1, 'ELEC-001', 'Wireless Headphones', 'Noise-cancelling over-ear headphones', 199.99, 120),
(1, 'ELEC-002', 'Smart Watch', 'Fitness tracking smart watch', 249.99, 80),
(2, 'APPR-001', 'Cotton T-Shirt', 'Plain cotton t-shirt', 19.99, 500),
(2, 'APPR-002', 'Denim Jacket', 'Classic denim jacket', 79.99, 150),
(3, 'HOME-001', 'Cast Iron Skillet', '12-inch cast iron skillet', 39.99, 200),
(3, 'HOME-002', 'Blender', 'High-speed kitchen blender', 89.99, 90),
(4, 'BOOK-001', 'Data Pipelines', 'Book on data engineering', 49.99, 60),
(4, 'BOOK-002', 'SQL Cookbook', 'Practical SQL recipes', 39.99, 75);

INSERT INTO orders (customer_id, status, subtotal, tax, shipping, total_amount, shipping_address) VALUES
(1, 'completed', 199.99, 16.00, 5.99, 221.98, '123 Main St, Austin, USA'),
(2, 'completed', 269.98, 21.60, 0.00, 291.58, '456 Oak Ave, Denver, USA'),
(3, 'shipped',   39.99,  3.20,  5.99, 49.18,  '789 Pine Rd, Seattle, USA'),
(4, 'processing', 89.99,  7.20,  5.99, 103.18, '321 Elm St, Portland, USA'),
(5, 'completed', 89.98,  7.20,  5.99, 103.17, '654 Maple Dr, Boston, USA'),
(1, 'cancelled', 49.99,  4.00,  0.00, 53.99,  '123 Main St, Austin, USA');

INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount) VALUES
(1, 1, 1, 199.99, 0.00),
(2, 1, 1, 199.99, 0.00),
(2, 4, 1, 69.99, 0.00),
(3, 5, 1, 39.99, 0.00),
(4, 6, 1, 89.99, 0.00),
(5, 8, 1, 39.99, 0.00),
(5, 7, 1, 49.99, 0.00),
(6, 7, 1, 49.99, 0.00);

INSERT INTO payments (order_id, payment_method, amount, currency, card_number, status) VALUES
(1, 'credit_card', 221.98, 'USD', '4111111111111111', 'completed'),
(2, 'credit_card', 291.58, 'USD', '5500000000000004', 'completed'),
(3, 'paypal',      49.18,  'USD', NULL,               'completed'),
(4, 'credit_card', 103.18, 'USD', '4111111111111111', 'authorized'),
(5, 'credit_card', 103.17, 'USD', '340000000000009',  'completed');

INSERT INTO inventory (product_id, warehouse_code, quantity_on_hand, reorder_level) VALUES
(1, 'WH-EAST', 40, 20),
(1, 'WH-WEST', 80, 20),
(2, 'WH-EAST', 30, 15),
(3, 'WH-EAST', 250, 100),
(4, 'WH-WEST', 150, 50),
(5, 'WH-EAST', 100, 40),
(6, 'WH-EAST', 90, 30),
(7, 'WH-WEST', 60, 20);

INSERT INTO reviews (product_id, customer_id, rating, comment) VALUES
(1, 1, 5, 'Great sound quality'),
(1, 2, 4, 'Very comfortable'),
(4, 3, 5, 'Fits perfectly'),
(6, 4, 4, 'Powerful motor'),
(7, 5, 5, 'Excellent reference');
