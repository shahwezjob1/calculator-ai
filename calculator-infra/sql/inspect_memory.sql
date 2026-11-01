-- Inspection queries for the calculator-ai Postgres instance.
-- Run inside the devcontainer, e.g.:  psql -U calculator -d calculator

-- Conversation threads (owned by calculator-agent)
SELECT thread_id, thread_name, created_at
FROM threads
ORDER BY created_at DESC
LIMIT 20;

-- Checkpoints per thread (LangGraph checkpointer tables)
SELECT thread_id, COUNT(*) AS checkpoints
FROM checkpoints
GROUP BY thread_id
ORDER BY checkpoints DESC
LIMIT 20;

-- Long-term memories (LangGraph store)
SELECT *
FROM store
LIMIT 20;

-- Custom constants (owned by calculator-service)
SELECT name, value, created_at, updated_at
FROM custom_constants
ORDER BY name;

-- Custom calculations and their review state (owned by calculator-service)
SELECT name, review_status, created_at, updated_at
FROM custom_calculations
ORDER BY name;
