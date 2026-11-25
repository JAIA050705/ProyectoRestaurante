-- =====================================================================
-- DB state test 2: EDGE CASES and CONSTRAINTS
-- Part A inserts rows that are valid but sit exactly on the limits
--         (they MUST be accepted).
-- Part B tries 18 invalid operations (they MUST be rejected by MySQL)
--         and prints a PASS/FAIL table.
-- All test rows are marked with 'QA-EDGE' / 'qa_edge' so that
-- 04_cleanup_test_data.sql can remove them.
-- Safe to re-run: it cleans its own rows first.
-- =====================================================================
USE restaurant_review_db;
SET SQL_SAFE_UPDATES = 0;

-- Remove rows of a previous run
DELETE FROM favorites WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'qa\_edge\_%');
DELETE FROM reviews   WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'qa\_edge\_%');
DELETE FROM restaurants WHERE name LIKE 'QA-EDGE%';
DELETE FROM users WHERE username LIKE 'qa\_edge\_%';
DROP TABLE IF EXISTS qa_results;
DROP PROCEDURE IF EXISTS qa_expect_failure;

-- =====================================================================
-- PART A - values on the limits (must be ACCEPTED)
-- =====================================================================

-- Users: username of exactly 50 characters, email of exactly 100
INSERT INTO users (username, email, password_hash) VALUES
    ('qa_edge_user_a', 'qa_edge_user_a@test.com', 'QA_HASH'),
    ('qa_edge_user_b', 'qa_edge_user_b@test.com', 'QA_HASH'),
    (CONCAT('qa_edge_', REPEAT('x', 42)), CONCAT('qa_edge_', REPEAT('e', 83), '@test.com'), 'QA_HASH');

-- Restaurants: price 1 and 4, name of 100 chars, address of 150 chars, accents, no reviews
INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES
    ('QA-EDGE cheapest',                'Test', 1, 'Tonala', 'QA-EDGE street 1'),
    ('QA-EDGE most expensive',          'Test', 4, 'Tonala', 'QA-EDGE street 2'),
    (CONCAT('QA-EDGE ', REPEAT('N', 92)), 'Test', 2, 'Tonala', REPEAT('A', 150)),
    ('QA-EDGE Taquería Ñandú Güero',    'Test', 2, 'Tonalá', 'QA-EDGE Calle Niños Héroes 3'),
    ('QA-EDGE without reviews',         'Test', 3, 'Tonala', 'QA-EDGE street 5');

-- Reviews: rating 1 and 5, no comment, comment of exactly 1000 characters
INSERT INTO reviews (user_id, restaurant_id, rating, comment)
SELECT u.id, r.id, 1, NULL
FROM users u, restaurants r
WHERE u.username = 'qa_edge_user_a' AND r.name = 'QA-EDGE cheapest';

INSERT INTO reviews (user_id, restaurant_id, rating, comment)
SELECT u.id, r.id, 5, REPEAT('c', 1000)
FROM users u, restaurants r
WHERE u.username = 'qa_edge_user_b' AND r.name = 'QA-EDGE cheapest';

INSERT INTO reviews (user_id, restaurant_id, rating, comment)
SELECT u.id, r.id, 5, 'Only review of this restaurant'
FROM users u, restaurants r
WHERE u.username = 'qa_edge_user_a' AND r.name = 'QA-EDGE most expensive';

-- A favorite
INSERT INTO favorites (user_id, restaurant_id)
SELECT u.id, r.id
FROM users u, restaurants r
WHERE u.username = 'qa_edge_user_a' AND r.name = 'QA-EDGE most expensive';

SELECT 'Part A OK: limit values accepted' AS result,
       (SELECT COUNT(*) FROM users       WHERE username LIKE 'qa\_edge\_%') AS users,
       (SELECT COUNT(*) FROM restaurants WHERE name     LIKE 'QA-EDGE%')    AS restaurants,
       (SELECT COUNT(*) FROM reviews     WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'qa\_edge\_%')) AS reviews;

-- =====================================================================
-- PART B - invalid operations (must be REJECTED)
-- qa_expect_failure runs the statement and records PASS if MySQL gave an
-- error, FAIL if the statement was accepted.
-- =====================================================================
CREATE TABLE qa_results (
    test_number INT AUTO_INCREMENT PRIMARY KEY,
    test_name   VARCHAR(120) NOT NULL,
    result      VARCHAR(10)  NOT NULL
);

DELIMITER $$
CREATE PROCEDURE qa_expect_failure(IN p_name VARCHAR(120), IN p_sql TEXT)
BEGIN
    DECLARE v_failed INT DEFAULT 0;
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_failed = 1;

    SET @qa_sql = p_sql;
    PREPARE qa_stmt FROM @qa_sql;
    EXECUTE qa_stmt;
    DEALLOCATE PREPARE qa_stmt;

    INSERT INTO qa_results (test_name, result)
    VALUES (p_name, IF(v_failed = 1, 'PASS', 'FAIL'));
END$$
DELIMITER ;

-- Unique constraints
CALL qa_expect_failure('duplicate username',
    'INSERT INTO users (username, email, password_hash) VALUES (''qa_edge_user_a'', ''other_a@test.com'', ''h'')');
CALL qa_expect_failure('duplicate email',
    'INSERT INTO users (username, email, password_hash) VALUES (''qa_edge_other'', ''qa_edge_user_a@test.com'', ''h'')');
CALL qa_expect_failure('same restaurant name and address twice',
    'INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES (''QA-EDGE cheapest'', ''Test'', 1, ''Tonala'', ''QA-EDGE street 1'')');
CALL qa_expect_failure('second review of the same restaurant by the same user',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT u.id, r.id, 3 FROM users u, restaurants r WHERE u.username = ''qa_edge_user_a'' AND r.name = ''QA-EDGE cheapest''');
CALL qa_expect_failure('same favorite twice',
    'INSERT INTO favorites (user_id, restaurant_id) SELECT u.id, r.id FROM users u, restaurants r WHERE u.username = ''qa_edge_user_a'' AND r.name = ''QA-EDGE most expensive''');

-- CHECK constraints
CALL qa_expect_failure('price_range 0',
    'INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES (''QA-EDGE price 0'', ''Test'', 0, ''Tonala'', ''QA-EDGE p0'')');
CALL qa_expect_failure('price_range 5',
    'INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES (''QA-EDGE price 5'', ''Test'', 5, ''Tonala'', ''QA-EDGE p5'')');
CALL qa_expect_failure('rating 0',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT u.id, r.id, 0 FROM users u, restaurants r WHERE u.username = ''qa_edge_user_b'' AND r.name = ''QA-EDGE most expensive''');
CALL qa_expect_failure('rating 6',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT u.id, r.id, 6 FROM users u, restaurants r WHERE u.username = ''qa_edge_user_b'' AND r.name = ''QA-EDGE most expensive''');

-- Foreign keys
CALL qa_expect_failure('review of a user that does not exist',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT 999999999, id, 3 FROM restaurants WHERE name = ''QA-EDGE cheapest''');
CALL qa_expect_failure('review of a restaurant that does not exist',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT id, 999999999, 3 FROM users WHERE username = ''qa_edge_user_b''');
CALL qa_expect_failure('favorite of a restaurant that does not exist',
    'INSERT INTO favorites (user_id, restaurant_id) SELECT id, 999999999 FROM users WHERE username = ''qa_edge_user_b''');
CALL qa_expect_failure('delete a restaurant that has reviews (RESTRICT)',
    'DELETE FROM restaurants WHERE name = ''QA-EDGE cheapest''');
CALL qa_expect_failure('delete a user that has reviews (RESTRICT)',
    'DELETE FROM users WHERE username = ''qa_edge_user_a''');

-- NOT NULL and column sizes
CALL qa_expect_failure('username NULL',
    'INSERT INTO users (username, email, password_hash) VALUES (NULL, ''null_user@test.com'', ''h'')');
CALL qa_expect_failure('rating NULL',
    'INSERT INTO reviews (user_id, restaurant_id, rating) SELECT u.id, r.id, NULL FROM users u, restaurants r WHERE u.username = ''qa_edge_user_b'' AND r.name = ''QA-EDGE most expensive''');
CALL qa_expect_failure('username of 51 characters (column is 50)',
    'INSERT INTO users (username, email, password_hash) VALUES (REPEAT(''u'', 51), ''long_user@test.com'', ''h'')');
CALL qa_expect_failure('restaurant name of 101 characters (column is 100)',
    'INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES (REPEAT(''N'', 101), ''Test'', 2, ''Tonala'', ''QA-EDGE long name'')');

-- Result table
SELECT test_number, test_name, result FROM qa_results ORDER BY test_number;
SELECT SUM(result = 'PASS') AS passed, SUM(result = 'FAIL') AS failed FROM qa_results;

DROP PROCEDURE IF EXISTS qa_expect_failure;
-- qa_results is kept so that run_db_tests.sh can read it; 04_cleanup_test_data.sql drops it.
