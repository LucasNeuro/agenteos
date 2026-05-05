"""Tool Agno: grava lead no Supabase e envia POST ao webhook (CARTÕES_LEADS / Maria)."""

from .lead_service import persist_lead_and_webhook


def registrar_lead_no_crm(
    lead_kind: str,
    nome: str,
    telefone: str,
    email: str = "Não informado",
    servico_solicitado: str = "",
    resumo_necessidade: str = "",
    potencial: str = "MEDIO",
    potencial_justificativa: str = "",
    caracteristicas_adicionais: str = "",
    tipo_imovel: str = "",
    tamanho_imovel: str = "",
    bairro_regiao: str = "",
    prazo: str = "",
    modo_imobiliario: str = "",
    intencao_imobiliario: str = "",
    tipo_servico_projeto: str = "",
    cidade_bairro_projeto: str = "",
    segmento_prestador: str = "",
    captacao_prestador: str = "",
    empresa_b2b: str = "",
    intencao_b2b: str = "",
    email_corporativo_b2b: str = "",
) -> str:
    """
    Regista o lead no mini CRM (Supabase) e envia o cartão JSON ao webhook se configurado.

    **Obrigatório ao encerrar** um fluxo útil (POP): chamar **neste turno** após encaminhamento ao humano/corretor
    ou após qualificação mínima — mesmo com dados parciais (usa "Não informado"). Um registo por fluxo encerrado,
    salvo correção explícita do cliente. Em WhatsApp, quando o estado de sessão traz **telefone_whatsapp**, usa-o em **telefone**.

    - **lead_kind**: `cliente_imobiliario` | `cliente_projetos` | `prestador_servico` | `imobiliaria_corretor`
    - **potencial**: `ALTO` | `MEDIO` | `BAIXO`
    - **intencao_imobiliario** / **modo_imobiliario** para mercado imobiliário conforme playbook.
    """
    return persist_lead_and_webhook(
        lead_kind,  # type: ignore[arg-type]
        nome,
        telefone,
        email=email,
        servico_solicitado=servico_solicitado,
        resumo_necessidade=resumo_necessidade,
        potencial=potencial,  # type: ignore[arg-type]
        potencial_justificativa=potencial_justificativa,
        caracteristicas_adicionais=caracteristicas_adicionais,
        tipo_imovel=tipo_imovel,
        tamanho_imovel=tamanho_imovel,
        bairro_regiao=bairro_regiao,
        prazo=prazo,
        modo_imobiliario=modo_imobiliario,
        intencao_imobiliario=intencao_imobiliario,
        tipo_servico_projeto=tipo_servico_projeto,
        cidade_bairro_projeto=cidade_bairro_projeto,
        segmento_prestador=segmento_prestador,
        captacao_prestador=captacao_prestador,
        empresa_b2b=empresa_b2b,
        intencao_b2b=intencao_b2b,
        email_corporativo_b2b=email_corporativo_b2b,
    )
