-- Maria CRM — id de sessão externa nos leads (dedupe stub automático)
-- Aplicar no Supabase após 001_maria_mini_crm.sql

alter table maria_leads
  add column if not exists source_external_session_id text;

create index if not exists maria_leads_source_ext_session_idx
  on maria_leads (source_external_session_id)
  where source_external_session_id is not null;
