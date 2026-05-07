-- Avaliações do agente Mistral AI Studio (classificação / JSON) vinculadas ao imóvel
-- Depende de 003_maria_imoveis_midias.sql (maria_imoveis, maria_imovel_midias)

create table if not exists public.maria_imovel_studio_assessments (
  id uuid primary key default gen_random_uuid(),
  imovel_id uuid not null references public.maria_imoveis (id) on delete cascade,
  -- Última mídia que disparou este run (opcional)
  trigger_midia_id uuid references public.maria_imovel_midias (id) on delete set null,
  -- Identificação da chamada Mistral
  mistral_conversation_id text,
  mistral_agent_id text,
  mistral_agent_version integer,
  -- Saída bruta do modelo (tipicamente JSON como texto)
  raw_output text,
  -- JSON parseado quando possível
  payload jsonb not null default '{}'::jsonb,
  -- IDs das mídias cujas URLs foram enviadas ao agente (ordem de envio)
  source_midia_ids uuid[] not null default '{}'::uuid[],
  source_image_urls text[] not null default '{}'::text[],
  status text not null default 'completed'::text
    check (status = any (array['pending'::text, 'completed'::text, 'failed'::text])),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists maria_imovel_studio_assessments_imovel_idx
  on public.maria_imovel_studio_assessments (imovel_id, created_at desc);

drop trigger if exists maria_imovel_studio_assessments_updated on public.maria_imovel_studio_assessments;
create trigger maria_imovel_studio_assessments_updated
  before update on public.maria_imovel_studio_assessments
  for each row execute function maria_set_updated_at();

alter table public.maria_imovel_studio_assessments enable row level security;

comment on table public.maria_imovel_studio_assessments is
  'Classificação / pré-avaliação via agente Mistral Studio (subagente); várias linhas por imóvel ao longo do tempo';
