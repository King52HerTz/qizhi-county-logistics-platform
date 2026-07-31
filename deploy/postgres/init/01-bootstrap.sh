#!/bin/sh
set -eu

psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set app_user="$APP_DB_USER" \
  --set app_password="$APP_DB_PASSWORD" <<'SQL'
create extension if not exists postgis;

select format('create role %I login password %L', :'app_user', :'app_password')
where not exists (select 1 from pg_roles where rolname = :'app_user')
\gexec

revoke all on schema public from public;
select format('grant usage, create on schema public to %I', :'app_user') \gexec
select format('grant connect on database %I to %I', current_database(), :'app_user') \gexec
select format('alter role %I set statement_timeout = %L', :'app_user', '30s') \gexec
select format('alter role %I set idle_in_transaction_session_timeout = %L', :'app_user', '30s') \gexec
SQL
