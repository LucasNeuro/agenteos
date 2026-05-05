-- Maria — cadastro de imóveis + mídias (Storage Supabase) + campos para visão/IA
-- Depende de 001_maria_mini_crm.sql (sessões, leads)

-- ---------------------------------------------------------------------------
-- Imóvel (rascunho vindo do WhatsApp ou futuro formulário; liga a sessão e opcionalmente a lead)
-- ---------------------------------------------------------------------------
create table if not exists maria_imoveis (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references maria_sessions (id) on delete set null,
  lead_id uuid references maria_leads (id) on delete set null,
  origem_canal text not null default 'whatsapp',
  -- Alinha com maria_lead_kind quando soubermos; null = ainda não classificado
  perfil_solicitante text check (
    perfil_solicitante is null
    or perfil_solicitante in (
      'cliente_imobiliario',
      'cliente_projetos',
      'imobiliaria_corretor',
      'prestador_servico',
      'desconhecido'
    )
  ),
  titulo_interno text,
  operacao text check (operacao is null or operacao in ('venda', 'locacao', 'outro')),
  tipo_imovel text,
  cidade text,
  bairro text,
  endereco_referencia text,
  metragem_texto text,
  valor_texto text,
  descricao_resumo text,
  status text not null default 'rascunho' check (status in ('rascunho', 'ativo', 'arquivado')),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists maria_imoveis_session_idx on maria_imoveis (session_id);
create index if not exists maria_imoveis_lead_idx on maria_imoveis (lead_id);
create index if not exists maria_imoveis_status_idx on maria_imoveis (status);
create index if not exists maria_imoveis_created_idx on maria_imoveis (created_at desc);

drop trigger if exists maria_imoveis_updated on maria_imoveis;
create trigger maria_imoveis_updated
  before update on maria_imoveis
  for each row execute function maria_set_updated_at();

-- ---------------------------------------------------------------------------
-- Mídias (object path no Storage + resultado opcional de visão)
-- ---------------------------------------------------------------------------
create table if not exists maria_imovel_midias (
  id uuid primary key default gen_random_uuid(),
  imovel_id uuid not null references maria_imoveis (id) on delete cascade,
  storage_bucket text not null,
  storage_path text not null,
  file_name text,
  mime_type text,
  byte_size bigint,
  source_channel text not null default 'whatsapp',
  whatsapp_message_id text,
  vision_provider text,
  vision_model text,
  vision_summary text,
  vision_labels jsonb not null default '[]',
  vision_raw jsonb,
  vision_error text,
  vision_at timestamptz,
  created_at timestamptz not null default now(),
  constraint maria_imovel_midias_bucket_path_uk unique (storage_bucket, storage_path)
);

create index if not exists maria_imovel_midias_imovel_idx on maria_imovel_midias (imovel_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Storage (bucket privado; upload via service_role na API)
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'maria-imoveis',
  'maria-imoveis',
  false,
  52428800,
  array['image/jpeg', 'image/png', 'image/webp', 'image/gif']::text[]
)
on conflict (id) do update set
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Políticas: utilizadores autenticados do Supabase Auth (futuro painel) podem ler/gerir;
-- anon sem acesso. Service role continua a ignorar RLS nas operações via API com service key.
drop policy if exists "maria_imoveis_storage_read_authenticated" on storage.objects;
create policy "maria_imoveis_storage_read_authenticated"
  on storage.objects for select to authenticated
  using (bucket_id = 'maria-imoveis');

drop policy if exists "maria_imoveis_storage_write_authenticated" on storage.objects;
create policy "maria_imoveis_storage_write_authenticated"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'maria-imoveis');

drop policy if exists "maria_imoveis_storage_update_authenticated" on storage.objects;
create policy "maria_imoveis_storage_update_authenticated"
  on storage.objects for update to authenticated
  using (bucket_id = 'maria-imoveis')
  with check (bucket_id = 'maria-imoveis');

drop policy if exists "maria_imoveis_storage_delete_authenticated" on storage.objects;
create policy "maria_imoveis_storage_delete_authenticated"
  on storage.objects for delete to authenticated
  using (bucket_id = 'maria-imoveis');

-- RLS nas tabelas novas (mesmo padrão do 001: anon bloqueado; backend com service_role)
alter table maria_imoveis enable row level security;
alter table maria_imovel_midias enable row level security;

comment on table maria_imoveis is 'Ficha de imóvel (rascunho ou ativo); vincula sessão WhatsApp e opcionalmente lead CRM';
comment on table maria_imovel_midias is 'Ficheiros no bucket maria-imoveis + metadados e análise de visão opcional';
