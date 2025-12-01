-- In psql, connected to wh_briefings as wh_user or another owner:
CREATE SCHEMA IF NOT EXISTS wh AUTHORIZATION wh_user;

-- Make sure your future tables live in that schema by default:
SET search_path TO wh, public;
