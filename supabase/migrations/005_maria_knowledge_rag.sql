-- Maria — RAG (Agno Knowledge): registo de conteúdos + chunks vectoriais
-- Embeddings: API Mistral (`mistral-embed`, 1024 dimensões) — não confundir com exemplos Supabase tipo gte-small (384).
-- Requer pgvector no projeto Supabase (Dashboard → Database → Extensions → vector).
-- Schema `ai` e nomes de tabela alinhados com Agno 2.x (PostgresDb + PgVector).

create extension if not exists vector;

create schema if not exists ai;

-- Tabela "contents" (metadados por ficheiro / URL) — espelha KNOWLEDGE_TABLE_SCHEMA do Agno
create table if not exists ai.maria_knowledge_contents (
  id text primary key,
  name text not null,
  description text not null,
  metadata jsonb,
  type text,
  size bigint,
  linked_to text,
  access_count bigint,
  status text,
  status_message text,
  created_at bigint,
  updated_at bigint,
  external_id text
);

create index if not exists idx_maria_knowledge_contents_name
  on ai.maria_knowledge_contents (name);

-- Tabela de chunks + embeddings (PgVector schema v1)
create table if not exists ai.maria_knowledge_vectors (
  id text primary key,
  name text,
  meta_data jsonb not null default '{}'::jsonb,
  filters jsonb default '{}'::jsonb,
  content text,
  embedding vector(1024),
  usage jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz,
  content_hash text,
  content_id text
);

create index if not exists idx_maria_knowledge_vectors_id on ai.maria_knowledge_vectors (id);
create index if not exists idx_maria_knowledge_vectors_name on ai.maria_knowledge_vectors (name);
create index if not exists idx_maria_knowledge_vectors_content_hash on ai.maria_knowledge_vectors (content_hash);
create index if not exists idx_maria_knowledge_vectors_content_id on ai.maria_knowledge_vectors (content_id);

-- Índice HNSW (distância coseno — padrão Agno PgVector com Mistral)
create index if not exists maria_knowledge_vectors_hnsw_index
  on ai.maria_knowledge_vectors
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 200);

comment on schema ai is 'RAG Maria (Agno): conteúdos e vetores; playbooks continuam no prompt da app';
comment on table ai.maria_knowledge_contents is 'Registo de documentos ingeridos (Knowledge contents DB)';
comment on table ai.maria_knowledge_vectors is 'Chunks e embeddings; consulta via search_knowledge_base no Agno';
