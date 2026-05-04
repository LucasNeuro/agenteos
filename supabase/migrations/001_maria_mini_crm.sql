-- Maria — Mini CRM (Postgres / Supabase)
-- Aplicar no SQL Editor do Supabase ou via CLI: supabase db push

-- Extensões
create extension if not exists "pgcrypto";

-- Tipos
do $$ begin
  create type maria_lead_kind as enum (
    'cliente_imobiliario',
    'cliente_projetos',
    'prestador_servico',
    'imobiliaria_corretor'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type maria_potencial_kind as enum ('ALTO', 'MEDIO', 'BAIXO');
exception when duplicate_object then null; end $$;

-- Sessões de conversa (liga ao canal / AgentOS quando existir id externo)
create table if not exists maria_sessions (
  id uuid primary key default gen_random_uuid(),
  external_session_id text unique,
  channel text not null default 'unknown',
  phone text,
  display_name text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists maria_sessions_phone_idx on maria_sessions (phone);
create index if not exists maria_sessions_created_idx on maria_sessions (created_at desc);

-- Mensagens / interações (histórico completo)
create table if not exists maria_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references maria_sessions (id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'tool')),
  content text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists maria_messages_session_idx on maria_messages (session_id, created_at);

-- Lead canónico (espelha o card JSON + webhook)
create table if not exists maria_leads (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references maria_sessions (id) on delete set null,
  lead_kind maria_lead_kind not null,
  nome text,
  telefone text,
  email text,
  servico_solicitado text,
  dados_imovel jsonb not null default '{}',
  resumo_necessidade text,
  potencial maria_potencial_kind,
  potencial_justificativa text,
  caracteristicas_adicionais text,
  webhook_payload jsonb,
  webhook_sent_at timestamptz,
  webhook_http_status int,
  webhook_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists maria_leads_kind_idx on maria_leads (lead_kind);
create index if not exists maria_leads_telefone_idx on maria_leads (telefone);
create index if not exists maria_leads_created_idx on maria_leads (created_at desc);

-- Detalhe: cliente final — imóvel
create table if not exists maria_lead_cliente_imobiliario (
  lead_id uuid primary key references maria_leads (id) on delete cascade,
  modo text check (modo in ('rapido', 'detalhado')),
  intencao text,
  tipo_imovel_resumo text,
  bairro_regiao text,
  prazo_necessidade text
);

-- Detalhe: cliente — projetos / arquitetura / obra / marcenaria
create table if not exists maria_lead_cliente_projetos (
  lead_id uuid primary key references maria_leads (id) on delete cascade,
  tipo_servico text,
  tipo_imovel text,
  faixa_m2 text,
  cidade_bairro text,
  prazo_inicio text
);

-- Detalhe: prestador / homologação
create table if not exists maria_lead_prestador (
  lead_id uuid primary key references maria_leads (id) on delete cascade,
  segmento text,
  captacao text
);

-- Detalhe: imobiliária ou corretor B2B
create table if not exists maria_lead_imobiliaria_b2b (
  lead_id uuid primary key references maria_leads (id) on delete cascade,
  empresa_ou_carteira text,
  intencao_b2b text,
  email_corporativo text
);

-- updated_at automático
create or replace function maria_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists maria_sessions_updated on maria_sessions;
create trigger maria_sessions_updated
  before update on maria_sessions
  for each row execute function maria_set_updated_at();

drop trigger if exists maria_leads_updated on maria_leads;
create trigger maria_leads_updated
  before update on maria_leads
  for each row execute function maria_set_updated_at();

-- RLS: backend usa service_role (ignora RLS). Bloqueia acesso público acidental.
alter table maria_sessions enable row level security;
alter table maria_messages enable row level security;
alter table maria_leads enable row level security;
alter table maria_lead_cliente_imobiliario enable row level security;
alter table maria_lead_cliente_projetos enable row level security;
alter table maria_lead_prestador enable row level security;
alter table maria_lead_imobiliaria_b2b enable row level security;

comment on table maria_leads is 'Lead principal Maria — alinhado ao card/webhook CARTÕES_LEADS';
comment on table maria_messages is 'Todas as interações para auditoria e mini CRM';
