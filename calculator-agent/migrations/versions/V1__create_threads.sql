-- Conversation thread registry (LangGraph has no thread list or name concept).
-- thread_id is the business key used as the LangGraph thread id; id is the surrogate pk.
CREATE TABLE IF NOT EXISTS threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
