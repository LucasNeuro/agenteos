-- Maria — bucket Storage dedicado a documentos para RAG (upload manual ou painel; ingest com service_role).
-- Os vectores ficam na migração 005 (schema ai + pgvector). Embeddings na app: Mistral API (mistral-embed, 1024 dims).

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'maria-rag-documents',
  'maria-rag-documents',
  false,
  20971520,
  array[
    'text/plain',
    'text/markdown',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]::text[]
)
on conflict (id) do update set
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "maria_rag_storage_read_authenticated" on storage.objects;
create policy "maria_rag_storage_read_authenticated"
  on storage.objects for select to authenticated
  using (bucket_id = 'maria-rag-documents');

drop policy if exists "maria_rag_storage_write_authenticated" on storage.objects;
create policy "maria_rag_storage_write_authenticated"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'maria-rag-documents');

drop policy if exists "maria_rag_storage_update_authenticated" on storage.objects;
create policy "maria_rag_storage_update_authenticated"
  on storage.objects for update to authenticated
  using (bucket_id = 'maria-rag-documents')
  with check (bucket_id = 'maria-rag-documents');

drop policy if exists "maria_rag_storage_delete_authenticated" on storage.objects;
create policy "maria_rag_storage_delete_authenticated"
  on storage.objects for delete to authenticated
  using (bucket_id = 'maria-rag-documents');
