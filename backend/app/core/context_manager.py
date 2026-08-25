"""Montagem de contexto: system prompt, histórico com resumo rolante
e mensagem do usuário enriquecida (imagem/documento).

O núcleo não conhece Ollama: a chamada de LLM para gerar resumos é
injetada via ``summarize_fn`` (texto -> texto).
"""

import re

HISTORY_LIMIT = 10
SUMMARY_REFRESH_DELTA = 8

SYSTEM_PROMPT = """Você é o StudyAgent, um tutor pessoal de estudos que roda localmente no computador do usuário.

Diretrizes:
- Responda SEMPRE em português do Brasil, de forma clara e didática.
- Modo padrão é TUTOR: guie o aluno passo a passo com perguntas e pistas, em vez de entregar a resposta final pronta.
- Se o usuário pedir explicitamente ("me dê a resposta", "resolva direto"), aí sim entregue a solução completa.
- Quando receber uma imagem da tela, descreva primeiro o que você identificou (matéria, tipo de conteúdo) antes de explicar.
- Use cálculos exatos quando possível e mostre o raciocínio.
- Se não tiver certeza sobre algo que viu na tela, diga o que vê e peça confirmação.
- Seja encorajador, mas honesto: aponte erros com clareza.

Modos disponíveis (o usuário pode pedir):
- professor: explicação detalhada do zero
- tutor: pistas e condução sem dar a resposta
- exercicios: gerar exercícios parecidos
- revisao: fazer perguntas para checar aprendizado
- resumo: condensar material
- simples: explicar como para um iniciante

Regras de honestidade:
- NUNCA invente fatos, datas, números, nomes ou notícias.
    - Se uma informação puder ter mudado com o tempo, ou você não tiver certeza, USE a ferramenta web_search antes de responder.
    - Se os resultados do web_search forem apenas links sem a resposta clara, USE open_url na página mais promissora para ler o conteúdo completo (ex.: placar de jogo, cotação, notícia recente).
    - Quando usar pesquisa, cite as fontes no formato [fonte: URL] e diga claramente o que veio da internet.
    - Se a pesquisa não trouxer resultado confiável, admita que não sabe em vez de chutar.
    - IMPORTANTE sobre documentos: quando a mensagem do aluno começar com "DOCUMENTO ANEXADO E DISPONÍVEL PARA LEITURA", o conteúdo completo está NA PRÓPRIA MENSAGEM — use-o e NUNCA peça para anexar nada. Peça para anexar com o botão 📎 APENAS quando essa linha NÃO estiver presente e ele citar um arquivo próprio (pdf/documento). Nesse caso, também NUNCA peça URL nem pesquise na internet por arquivos dele."""

SUMMARY_PROMPT = """Atualize o resumo desta sessão de estudos.

Resumo anterior:
{previous}

Mensagens novas (mais antigas que a janela recente):
{transcript}

Escreva o resumo atualizado em português com esta estrutura obrigatória:
FATOS IMPORTANTES: nome do aluno, datas de provas/trabalhos, metas e compromissos citados (se existirem).
CONTEÚDO ESTUDADO: matérias e tópicos com pontos-chave.
DIFICULDADES E PRÓXIMOS PASSOS: dificuldades do aluno e pendências.

Regras: no máximo 12 linhas; preserve nomes, datas e números EXATAMENTE como foram citados;
nunca invente informações; responda APENAS com o texto do resumo, sem prefixos,
saudações ou comentários."""


def build_document_block(name: str, pages: int, body: str) -> str:
    return (
        f"DOCUMENTO ANEXADO E DISPONÍVEL PARA LEITURA: '{name}' "
        f"({pages} páginas). Conteúdo:\n\n{body}"
    )


def build_image_note(camera: bool) -> str:
    origem = "minha câmera" if camera else "minha tela"
    return (
        f"(A imagem anexada é uma captura de {origem}. Se a pergunta "
        "for sobre a tela ou o que está visível nela, responda com "
        "base NA IMAGEM.)"
    )


def whole_doc_body(text: str) -> str:
    return f"Conteúdo COMPLETO do documento:\n\n{text}\n\n[fim do documento]"


def digest_body(digest: str) -> str:
    return (
        "Dossiê do documento inteiro (resumo de todas as partes,"
        " gerado página por página):\n"
        f"{digest}"
    )


def excerpts_body(excerpts: str) -> str:
    return f"Trechos relevantes:\n{excerpts}"


class ContextManager:
    def __init__(self, memory, summarize_fn):
        self.memory = memory
        self._summarize = summarize_fn

    def assemble(self, session_id: str, user_message: str) -> list[dict]:
        """Monta [system(+resumo), *histórico, user] para enviar ao modelo."""
        history = self.memory.history(session_id, limit=HISTORY_LIMIT)
        summary = self._rolling_summary(session_id)
        system_content = SYSTEM_PROMPT
        if summary:
            system_content += (
                f"\n\nResumo do que já foi conversado nesta sessão:\n{summary}"
            )
        messages = [{"role": "system", "content": system_content}, *history]
        messages.append({"role": "user", "content": user_message})
        return messages

    def _rolling_summary(self, session_id: str):
        total = self.memory.count_messages(session_id)
        if total <= HISTORY_LIMIT + SUMMARY_REFRESH_DELTA:
            return None
        entry = self.memory.get_summary(session_id)
        # msg_count = nº de mensagens antigas já cobertas pelo resumo;
        # regera só quando >= DELTA mensagens ficaram fora da janela E do resumo.
        needs_refresh = entry is None or (
            total - entry["msg_count"] >= HISTORY_LIMIT + SUMMARY_REFRESH_DELTA
        )
        if not needs_refresh:
            return entry["summary"]
        older = self.memory.history_head(
            session_id, max(total - HISTORY_LIMIT, 0)
        )
        if not older:
            return entry["summary"] if entry else None
        transcript = "\n".join(
            f"{'aluno' if m['role'] == 'user' else 'tutor'}: {m['content'][:400]}"
            for m in older
        )
        summary_text = self._summarize(
            SUMMARY_PROMPT.format(
                previous=entry["summary"] if entry else "(nenhum)",
                transcript=transcript,
            )
        ).strip()
        summary_text = re.sub(r"^(assistant|user|tutor)\s*[:\-]?\s*", "", summary_text).strip()
        self.memory.set_summary(session_id, summary_text, total - HISTORY_LIMIT)
        return summary_text
