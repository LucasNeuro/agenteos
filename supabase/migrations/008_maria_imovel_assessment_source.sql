-- Amplia avaliações de imóvel: origem Mari+Serp (além de registos legados sem coluna).
-- Depende de 007_maria_imovel_studio_assessment.sql

alter table public.maria_imovel_studio_assessments
  add column if not exists assessment_source text;

comment on column public.maria_imovel_studio_assessments.assessment_source is
  'mari_serp = tool manual com pesquisa; mari_serp_enrich = auto segundo plano com Serp; mari_auto_enrich = auto só visão/contexto; mistral_studio = legado; vazio = legado';

comment on table public.maria_imovel_studio_assessments is
  'Pré-avaliações por imóvel — Mari + pesquisa web (SerpAPI) e/ou legado; várias linhas ao longo do tempo';
