-- Initialize PostgreSQL with pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema
CREATE SCHEMA IF NOT EXISTS voice_to_task;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA voice_to_task TO voicetask;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA voice_to_task TO voicetask;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA voice_to_task TO voicetask;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Voice-to-Task database initialized with pgvector extension';
END $$;
