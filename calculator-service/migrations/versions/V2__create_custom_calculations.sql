-- Custom calculations: user-authored scripts in the restricted Python subset.
-- params holds [{"name": ..., "description": ...}] descriptors (JSONB: document-shaped,
-- 1:1 lifecycle with the row). review_notes stores the last LLM review response.
CREATE TABLE IF NOT EXISTS custom_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL UNIQUE,
    description VARCHAR(1024) NOT NULL,
    script TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '[]',
    review_status VARCHAR(20) NOT NULL,
    review_notes JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
