-- First-boot init scripts live here (mounted at docker-entrypoint-initdb.d).
-- They run exactly once, when the Postgres data directory is empty.
--
-- App tables are owned by each service's own migrations (applied via startup.sh),
-- and LangGraph creates its own tables via setup(). Nothing to seed yet.
SELECT 1;
