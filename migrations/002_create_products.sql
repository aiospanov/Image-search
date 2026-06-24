-- Migration 002: products table for PostgreSQL enrichment step

CREATE TABLE IF NOT EXISTS products (
    id          TEXT         PRIMARY KEY,
    name        TEXT         NOT NULL,
    price       NUMERIC      NOT NULL,
    image_url   TEXT,
    category    TEXT,
    brand       TEXT,
    in_stock    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products (in_stock);
