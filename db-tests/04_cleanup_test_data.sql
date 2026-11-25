-- =====================================================================
-- Removes ONLY the rows created by the tests; your own data stays.
--   * 02_edge_cases.sql   -> username 'qa_edge_...', restaurants 'QA-EDGE...'
--   * 03_massive_data.sql -> users 'load_user_...', restaurants 'LOAD Restaurant ...'
--   * the REST tests (JUnit) -> users 'qa_...', restaurants with address 'Calle QA ...'
-- =====================================================================
USE restaurant_review_db;
SET SQL_SAFE_UPDATES = 0;

DROP TABLE IF EXISTS qa_results;
DROP PROCEDURE IF EXISTS qa_expect_failure;

-- Children first
DELETE FROM favorites
WHERE user_id IN (SELECT id FROM users
                  WHERE username LIKE 'qa\_%' OR username LIKE 'load\_user\_%')
   OR restaurant_id IN (SELECT id FROM restaurants
                        WHERE name LIKE 'QA-EDGE%' OR name LIKE 'LOAD Restaurant %'
                           OR address LIKE 'Calle QA %');

DELETE FROM reviews
WHERE user_id IN (SELECT id FROM users
                  WHERE username LIKE 'qa\_%' OR username LIKE 'load\_user\_%')
   OR restaurant_id IN (SELECT id FROM restaurants
                        WHERE name LIKE 'QA-EDGE%' OR name LIKE 'LOAD Restaurant %'
                           OR address LIKE 'Calle QA %');

DELETE FROM restaurants
WHERE name LIKE 'QA-EDGE%' OR name LIKE 'LOAD Restaurant %' OR address LIKE 'Calle QA %';

DELETE FROM users
WHERE username LIKE 'qa\_%' OR username LIKE 'load\_user\_%';

SELECT 'users' AS table_name, COUNT(*) AS total FROM users
UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants
UNION ALL SELECT 'reviews',     COUNT(*) FROM reviews
UNION ALL SELECT 'favorites',   COUNT(*) FROM favorites;
