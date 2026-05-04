# Supabase — Maria Mini CRM

1. No [Supabase Dashboard](https://supabase.com/dashboard) do projeto, abre **SQL Editor**.
2. Cola e executa o ficheiro `migrations/001_maria_mini_crm.sql` (todo o conteúdo).
3. Confirma que as tabelas `maria_sessions`, `maria_messages`, `maria_leads` e as `maria_lead_*` existem em **Table Editor**.

O backend usa a **service_role** com a REST API (`/rest/v1/`). Não uses esta chave em browser ou apps móveis.

Se o erro `execute function` / trigger aparecer na tua versão do Postgres, altera nas últimas linhas para `execute procedure maria_set_updated_at()` conforme a documentação da tua instância.
