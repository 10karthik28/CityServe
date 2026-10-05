-- ============================================================
--  Kerala CityServe – MySQL Schema
--  Import this file in phpMyAdmin:
--    Database: cityserve  →  Import  →  choose this file
-- ============================================================

CREATE DATABASE IF NOT EXISTS cityserve
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cityserve;

-- ----------------------------------------------------------------
-- Registered citizens
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    phone         VARCHAR(20)  DEFAULT '',
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------
-- Department authority accounts (seeded below)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS authorities (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    department    VARCHAR(100) NOT NULL
);

-- ----------------------------------------------------------------
-- Field personnel managed by an authority
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personnel (
    id           INT         AUTO_INCREMENT PRIMARY KEY,
    authority_id INT         NOT NULL,
    name         VARCHAR(100) NOT NULL,
    phone        VARCHAR(20)  NOT NULL,
    FOREIGN KEY (authority_id) REFERENCES authorities(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------
-- Citizen service requests
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issues (
    id           INT          AUTO_INCREMENT PRIMARY KEY,
    issue_number VARCHAR(20)  NOT NULL UNIQUE,
    user_id      INT          NOT NULL,
    category     VARCHAR(100) NOT NULL,
    description  TEXT         NOT NULL,
    location     VARCHAR(300) NOT NULL,
    lat          FLOAT        DEFAULT NULL,
    lng          FLOAT        DEFAULT NULL,
    status       VARCHAR(50)  DEFAULT 'Requested to the authority',
    personnel_id INT          DEFAULT NULL,
    image_path            VARCHAR(255) DEFAULT NULL,
    completion_image_path VARCHAR(255) DEFAULT NULL,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)      REFERENCES users(id)     ON DELETE CASCADE,
    FOREIGN KEY (personnel_id) REFERENCES personnel(id) ON DELETE SET NULL
);

-- ----------------------------------------------------------------
-- Ratings submitted after work is done
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id         INT      AUTO_INCREMENT PRIMARY KEY,
    issue_id   INT      NOT NULL,
    user_id    INT      NOT NULL,
    rating     TINYINT  NOT NULL,
    comments   TEXT     DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
    UNIQUE KEY unique_feedback (issue_id, user_id)   -- one rating per issue per user
);
