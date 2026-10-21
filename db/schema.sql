-- Dashboard database (Supabase Postgres, free tier). Loaded by db/load.py from saved files.
-- Full review_text is not stored; evidence_quote + IDs are enough for drill-down.
create table if not exists records (
  review_id text primary key, source_sha256 text not null, status text not null, reason text,
  topic text, intent text, severity int, sentiment real, entities jsonb, evidence_quote text,
  needs_review boolean, label_config text, cache_source_id text,
  review_rating text, review_timestamp text, app_version text);
create table if not exists issues (issue_id text primary key, topic text, subtopic text, name text,
  description text, member_count int, map_version text);
create table if not exists membership (issue_id text not null, review_id text not null, primary key (issue_id, review_id));
create table if not exists ranking (rank int primary key, issue_id text unique not null, complaint_count int,
  severity_sum int, mean_severity text, priority_score int);
create table if not exists aggregates (topic text primary key, records int, complaint_or_cancellation int,
  cancellation int, severity_sum int, severity_4_plus int, needs_review int);
create table if not exists claims (claim_id text primary key, issue_id text, metric text, value text);
create table if not exists memo (id int primary key, recommendation text, memo_markdown text, cited_review_ids jsonb);
create table if not exists run_summary (key text primary key, value jsonb);
create index if not exists membership_issue on membership(issue_id);

do $$ declare t text; begin
  foreach t in array array['records','issues','membership','ranking','aggregates','claims','memo','run_summary'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists anon_read on %I', t);
    execute format('create policy anon_read on %I for select to anon using (true)', t);
    execute format('revoke insert, update, delete, truncate on %I from anon', t);
  end loop;
end $$;
