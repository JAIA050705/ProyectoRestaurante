-- =====================================================================
-- DB state test 3: MASSIVE DATA
-- Loads 5,000 users, 1,000 restaurants and 25,000 reviews
-- (every user reviews 5 different restaurants, ratings 1 to 5).
-- Use it to see how the API behaves with a lot of data:
--   * GET /api/reviews has no pagination, so it returns ALL the rows.
--     Measure the time and size of the answer in Bruno (bottom of the response).
--   * GET /api/reviews?restaurantId=N and /api/restaurants/N/rating must stay fast
--     thanks to idx_reviews_restaurant.
-- All rows are marked 'load_user_', 'LOAD Restaurant' so that
-- 04_cleanup_test_data.sql can remove them. Safe to re-run.
-- Needs MySQL 8 (recursive CTE and window functions).
-- =====================================================================
USE restaurant_review_db;
SET SQL_SAFE_UPDATES = 0;
SET SESSION cte_max_recursion_depth = 100000;

-- Remove a previous load
DELETE FROM favorites WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'load\_user\_%');
DELETE FROM reviews   WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'load\_user\_%');
DELETE FROM restaurants WHERE name LIKE 'LOAD Restaurant %';
DELETE FROM users WHERE username LIKE 'load\_user\_%';

-- 5,000 users
INSERT INTO users (username, email, password_hash)
WITH RECURSIVE seq (n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < 5000
)
SELECT CONCAT('load_user_', n), CONCAT('load_user_', n, '@load.test'), 'LOAD_HASH'
FROM seq;

-- 1,000 restaurants
INSERT INTO restaurants (name, cuisine, price_range, city, address)
WITH RECURSIVE seq (n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < 1000
)
SELECT CONCAT('LOAD Restaurant ', n),
       ELT(1 + n MOD 5, 'Mexican', 'Italian', 'Japanese', 'French', 'Seafood'),
       1 + n MOD 4,
       ELT(1 + n MOD 3, 'Guadalajara', 'Zapopan', 'Tonala'),
       CONCAT('Load Street ', n)
FROM seq;

-- 25,000 reviews: user number u reviews 5 restaurants, always different ones
INSERT INTO reviews (user_id, restaurant_id, rating, comment)
SELECT u.id,
       r.id,
       1 + (u.un + ks.k) MOD 5,
       CONCAT('Load test review ', u.un, '-', ks.k)
FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS un
      FROM users WHERE username LIKE 'load\_user\_%') AS u
JOIN (SELECT 0 AS k UNION ALL SELECT 1 UNION ALL SELECT 2
      UNION ALL SELECT 3 UNION ALL SELECT 4) AS ks
JOIN (SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn
      FROM restaurants WHERE name LIKE 'LOAD Restaurant %') AS r
  ON r.rn = ((u.un * 7 + ks.k * 131) MOD 1000) + 1;

-- A few favorites for the first load users
INSERT INTO favorites (user_id, restaurant_id)
SELECT r.user_id, r.restaurant_id
FROM reviews r
JOIN users u ON u.id = r.user_id
WHERE u.username LIKE 'load\_user\_%' AND r.rating = 5
LIMIT 2000;

-- Check
SELECT 'users'       AS table_name, COUNT(*) AS total FROM users       WHERE username LIKE 'load\_user\_%'
UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants WHERE name LIKE 'LOAD Restaurant %'
UNION ALL SELECT 'reviews',     COUNT(*) FROM reviews     WHERE comment LIKE 'Load test review %'
UNION ALL SELECT 'favorites',   COUNT(*) FROM favorites   WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'load\_user\_%');
-- Expected: 5000, 1000, 25000 and 2000.

-- How the average of one restaurant looks (what /restaurants/{id}/rating computes)
SELECT r.name, COUNT(*) AS total_reviews, ROUND(AVG(v.rating), 2) AS average_rating
FROM restaurants r JOIN reviews v ON v.restaurant_id = r.id
WHERE r.name = 'LOAD Restaurant 1'
GROUP BY r.id, r.name;
