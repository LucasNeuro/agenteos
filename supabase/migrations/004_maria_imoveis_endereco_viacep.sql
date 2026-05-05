-- Maria — endereço completo + payload ViaCEP + ordem das mídias (várias fotos por imóvel)
-- Aplicar após 003_maria_imoveis_midias.sql

-- ---------------------------------------------------------------------------
-- Imóvel: localização precisa (ViaCEP API pública https://viacep.com.br/)
-- ---------------------------------------------------------------------------
alter table maria_imoveis
  add column if not exists cep text,
  add column if not exists logradouro text,
  add column if not exists numero text,
  add column if not exists complemento text,
  add column if not exists uf text,
  add column if not exists ibge text,
  add column if not exists endereco_livre_cliente text,
  add column if not exists viacep_consultado_em timestamptz,
  add column if not exists viacep_payload jsonb not null default '{}';

comment on column maria_imoveis.viacep_payload is 'Resposta JSON bruta do ViaCEP (ws/{cep}/json/) para auditoria e confirmação humana';
comment on column maria_imoveis.endereco_livre_cliente is 'Texto livre digitado pelo cliente (endereço completo antes da normalização)';

create index if not exists maria_imoveis_cep_idx on maria_imoveis (cep) where cep is not null;

-- ---------------------------------------------------------------------------
-- Mídias: ordem das fotos no mesmo imóvel (0 = primeira)
-- ---------------------------------------------------------------------------
alter table maria_imovel_midias
  add column if not exists ordem int not null default 0;

create index if not exists maria_imovel_midias_imovel_ordem_idx on maria_imovel_midias (imovel_id, ordem);
