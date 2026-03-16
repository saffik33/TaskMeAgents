-- Initialize databases for TaskMeAgents local development
-- This script runs on first PostgreSQL startup only

-- Create the app database (Temporal's 'temporal' DB is auto-created by temporalio/auto-setup)
SELECT 'CREATE DATABASE "TaskMeAgents"' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'TaskMeAgents')\gexec

-- Connect to the app database and create the schema
\c "TaskMeAgents"
CREATE SCHEMA IF NOT EXISTS taskme_agents;
