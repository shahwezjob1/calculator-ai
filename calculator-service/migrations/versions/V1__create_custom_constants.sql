-- Custom constants: name -> value pairs resolved by the agent's expression evaluator.
-- UNIQUE on name already creates the B-tree index; no separate CREATE INDEX needed.
CREATE TABLE IF NOT EXISTS custom_constants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL UNIQUE,
    value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
