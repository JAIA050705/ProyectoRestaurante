-- =====================================================================
-- DB state test 1: EMPTY TABLES
-- Leaves the four tables completely empty to check how the API behaves
-- with no data at all.
--
-- WARNING: deletes ALL rows. Use it only on your development database.
-- To get the sample data back, run restaurant_review_schema.sql again
-- (and seed_passwords.sql if you want to log in as the sample users).
-- =====================================================================
USE restaurant_review_db;

SET SQL_SAFE_UPDATES = 0;   -- Workbench blocks DELETE without WHERE otherwise

-- Children first, because of the foreign keys
DELETE FROM favorites;
DELETE FROM reviews;
DELETE FROM restaurants;
DELETE FROM users;

SELECT 'users' AS table_name, COUNT(*) AS total FROM users
UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants
UNION ALL SELECT 'reviews',     COUNT(*) FROM reviews
UNION ALL SELECT 'favorites',   COUNT(*) FROM favorites;

-- ---------------------------------------------------------------------
-- What the API must do now (check it in Bruno):
--   GET  /api/restaurants              -> 200 and []   (not a 500)
--   GET  /api/reviews                  -> 200 and []
--   GET  /api/restaurants/1            -> 404
--   GET  /api/restaurants/1/rating     -> 404
--   POST /api/auth/login (any user)    -> 401 (no users exist)
--   POST /api/auth/register            -> 201 (the first user gets id 1 or the next id)
--   After registering: POST /api/restaurants -> 201, GET /api/users/{id}/favorites -> 200 and []
-- ---------------------------------------------------------------------
