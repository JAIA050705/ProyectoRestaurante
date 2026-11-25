-- =====================================================================
-- Restaurant Review Platform API - Part 1: Schema + sample data
-- Target: MySQL 8.4 (CHECK constraints require 8.0.16+)
-- Safe to re-run: tables are dropped and recreated in FK-safe order.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS restaurant_review_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE restaurant_review_db;

-- ---------------------------------------------------------------------
-- Drop existing tables (children first)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS restaurants;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------------
-- users: people who register to leave reviews
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,   -- never store plain passwords
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- restaurants: the places being reviewed
-- price_range: 1 = $, 2 = $$, 3 = $$$, 4 = $$$$
-- ---------------------------------------------------------------------
CREATE TABLE restaurants (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100) NOT NULL,
    cuisine     VARCHAR(50)  NOT NULL,
    price_range TINYINT UNSIGNED NOT NULL,
    city        VARCHAR(80)  NOT NULL,
    address     VARCHAR(150) NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    -- The same name at the same address cannot be registered twice
    -- (the API answers 409 Conflict when this is violated)
    UNIQUE KEY uq_restaurants_name_address (name, address),
    KEY idx_restaurants_city (city),
    KEY idx_restaurants_cuisine (cuisine),
    CONSTRAINT chk_restaurants_price CHECK (price_range BETWEEN 1 AND 4)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- reviews: main resource, connects users with restaurants
-- * One review per user per restaurant (UNIQUE) -> 409 Conflict in the API
-- * ON DELETE RESTRICT: reviews are never deleted, so a user or
--   restaurant that has reviews cannot be removed by accident
-- ---------------------------------------------------------------------
CREATE TABLE reviews (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       INT UNSIGNED NOT NULL,
    restaurant_id INT UNSIGNED NOT NULL,
    rating        TINYINT UNSIGNED NOT NULL,
    comment       TEXT         NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_reviews_user_restaurant (user_id, restaurant_id),
    KEY idx_reviews_restaurant (restaurant_id),
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_reviews_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- favorites: restaurants a user saved
-- This is the resource that supports the DELETE web service.
-- ---------------------------------------------------------------------
CREATE TABLE favorites (
    user_id       INT UNSIGNED NOT NULL,
    restaurant_id INT UNSIGNED NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, restaurant_id),
    CONSTRAINT fk_favorites_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_favorites_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- Sample data (fictional)
-- password_hash values are placeholders, NOT real hashes. Replace them
-- with real hashes (e.g. BCrypt) once login is implemented.
-- =====================================================================

INSERT INTO users (username, email, password_hash) VALUES
    ('maria_g',  'maria@example.com',  'PLACEHOLDER_HASH_1'),
    ('carlos_r', 'carlos@example.com', 'PLACEHOLDER_HASH_2'),
    ('ana_l',    'ana@example.com',    'PLACEHOLDER_HASH_3'),
    ('luis_m',   'luis@example.com',   'PLACEHOLDER_HASH_4'),
    ('sofia_p',  'sofia@example.com',  'PLACEHOLDER_HASH_5');

INSERT INTO restaurants (name, cuisine, price_range, city, address) VALUES
    ('La Casona Dorada',   'Mexican',  3, 'Guadalajara', 'Av. Chapultepec 120'),
    ('Sakura Garden',      'Japanese', 3, 'Guadalajara', 'Calle Libertad 45'),
    ('Taquería El Güero',  'Mexican',  1, 'Tonalá',      'Av. Tonaltecas 310'),
    ('Trattoria Bella',    'Italian',  2, 'Zapopan',     'Av. Patria 880'),
    ('Le Petit Bistro',    'French',   4, 'Guadalajara', 'Av. Vallarta 2050'),
    ('Mariscos La Playa',  'Seafood',  2, 'Zapopan',     'Calle Hidalgo 77');

INSERT INTO reviews (user_id, restaurant_id, rating, comment) VALUES
    (1, 1, 5, 'Excellent service and amazing mole. Worth every peso.'),
    (2, 1, 4, 'Great atmosphere, a bit slow on busy nights.'),
    (3, 1, 5, 'Best birthday dinner we have had.'),
    (1, 2, 3, 'Fresh fish but the portions were small.'),
    (2, 2, 4, 'Good sushi and very clean place.'),
    (4, 3, 2, 'Tacos were cold when they arrived.'),
    (5, 3, 3, 'Cheap and tasty, but the line is long.'),
    (3, 4, 5, 'The carbonara is perfect.'),
    (4, 4, 4, 'Cozy place with friendly staff.'),
    (5, 5, 4, 'Elegant and delicious, but expensive.'),
    (1, 6, 5, 'The shrimp cocktail is unbeatable.'),
    (2, 6, 4, 'Fresh seafood and generous portions.');

INSERT INTO favorites (user_id, restaurant_id) VALUES
    (1, 1),
    (1, 4),
    (2, 1),
    (3, 4),
    (5, 6);

-- =====================================================================
-- Quick checks (run these after the script to verify everything loaded)
-- =====================================================================

-- Row counts per table
SELECT 'users' AS table_name, COUNT(*) AS total FROM users
UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants
UNION ALL SELECT 'reviews',     COUNT(*) FROM reviews
UNION ALL SELECT 'favorites',   COUNT(*) FROM favorites;

-- Average rating per restaurant (the query behind GET /restaurants/{id}/rating)
SELECT r.id,
       r.name,
       ROUND(AVG(rv.rating), 2) AS avg_rating,
       COUNT(rv.id)             AS total_reviews
FROM restaurants r
LEFT JOIN reviews rv ON rv.restaurant_id = r.id
GROUP BY r.id, r.name
ORDER BY avg_rating DESC;
