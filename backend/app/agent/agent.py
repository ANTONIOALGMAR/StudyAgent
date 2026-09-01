import base64
import logging
import re

from ..core.context_manager import (
    ContextManager,
    build_document_block,
    digest_body,
    excerpts_body,
    whole_doc_body,
)
from ..core.model_manager import available_models
from ..core.orchestrator.evidence import EvidenceStore
from ..core.orchestrator.validator import ResponseValidator
from ..core.memory_manager import CognitiveMemory
from ..core.planner import (
    WHOLE_DOC_MAX_CHARS,
    build_plan,
    is_social_greeting,
)
from ..core.registered_tools import calculate_tool, open_url_tool, web_search_tool  # noqa: F401
from ..core.tool_registry import all_schemas, get
from ..core.vision_router import (
    VisionContext,
    VisionIntent,
    build_image_note,
    decide_ocr_block,
    format_window_note,
)
from ..security.permissions import PermissionDeniedError
from ..vision import ocr, screen, window
from ..vision.engine import process_capture
from ..vision.screen import ScreenManager
from .llm import chat, chat_with_tools
from .memory import Memory

log = logging.getLogger("studyagent.vision")


class StudyAgent:
    def __init__(self):
        self.memory = Memory()
        self.cognitive_memory = CognitiveMemory()
        self.ctx = ContextManager(
            self.memory,
            summarize_fn=lambda prompt: chat([{"role": "system", "content": prompt}]),
        )
        self._digest_cache: dict[str, str] = {}
        self._session_docs: dict[str, str] = {}

    def _remember_object_from_message(self, message: str) -> None:
        if not message or not message.strip():
            return

        text = message.strip()
        known_objects = [
            "celular", "telefone", "chave", "mochila", "livro", "caderno",
            "carregador", "mouse", "teclado", "notebook", "agenda", "fone",
            "relógio", "garrafa", "caneta", "caderno", "laptop"
        ]
        lowered = text.lower()
        rooms = [
            "quarto", "sala", "cozinha", "banheiro", "escritório", "escritorio",
            "garagem", "varanda", "biblioteca", "mesa", "estante", "prateleira",
            "armário", "armario"
        ]
        room = None
        for room_name in rooms:
            if room_name in lowered:
                room = room_name
                break

        for obj in known_objects:
            patterns = [
                rf"(?:meu|minha|o|a|um|uma)?\s*{re.escape(obj)}\s*(?:está|fica|está em|está na|está no|deixei|deixei em|deixei na|deixei no|coloquei|guardei|guardei em|guardei na|guardei no)\s*(?:em|na|no|sobre|sobre a|sobre o)?\s*(.+?)(?:[.!?]|$)",
                rf"(?:deixei|guardei|coloquei)\s*(?:meu|minha|o|a|um|uma)?\s*{re.escape(obj)}\s*(?:em|na|no|sobre)\s*(.+?)(?:[.!?]|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, lowered)
                if match:
                    location = match.group(1).strip()
                    if len(location) > 2 and len(location) < 180:
                        semantic_area = self._extract_semantic_area(location, room)
                        self.memory.remember_object_location(
                            obj,
                            location,
                            room=room,
                            area=semantic_area or room or location,
                            context=text,
                        )
                    return
        return

    def _extract_object_name(self, message: str) -> str | None:
        lowered = (message or "").lower()
        for obj in [
            "celular", "telefone", "chave", "mochila", "livro", "caderno",
            "carregador", "mouse", "teclado", "notebook", "agenda", "fone",
            "relógio", "garrafa", "caneta", "laptop"
        ]:
            if obj in lowered:
                return obj
        return None

    def _is_object_location_request(self, message: str) -> bool:
        if not message or not message.strip():
            return False
        lowered = message.lower()
        if not any(token in lowered for token in ["onde está", "onde fica", "localize", "localizar", "encontre", "achar", "procure", "procura", "onde está o", "onde está a", "onde fica o", "onde fica a"]):
            return False
        return self._extract_object_name(message) is not None

    def _extract_room_hint(self, message: str) -> str | None:
        lowered = (message or "").lower()
        for room_name in [
            "quarto", "sala", "cozinha", "banheiro", "escritório", "escritorio",
            "garagem", "varanda", "biblioteca", "entrada", "escritório", "armário", "armario",
            "mesa", "prateleira", "estante", "cômodo", "comodo"
        ]:
            if room_name in lowered:
                return room_name
        return None

    def _extract_area_hint(self, message: str) -> str | None:
        lowered = (message or "").lower()
        for area_name in [
            "mesa da direita", "mesa da esquerda", "mesa de canto", "prateleira da parede",
            "prateleira da esquerda", "prateleira da direita", "armário da esquerda", "armario da esquerda",
            "armário da direita", "armario da direita", "canto da sala", "canto do quarto",
            "gaveta", "baia", "debaixo da mesa", "em cima da mesa"
        ]:
            if area_name in lowered:
                return area_name
        return None

    def _extract_semantic_area(self, location: str, room: str | None = None) -> str:
        text = (location or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        semantic_matches = [
            "mesa da direita", "mesa da esquerda", "mesa de canto",
            "prateleira da direita", "prateleira da esquerda", "prateleira da parede",
            "prateleira", "armário da direita", "armario da direita",
            "armário da esquerda", "armario da esquerda", "canto da sala", "canto do quarto",
            "gaveta", "baia", "debaixo da mesa", "embaixo da mesa", "em cima da mesa",
            "sobre a mesa", "sobre o criado-mudo", "criado-mudo", "cadeira"
        ]
        for area_name in semantic_matches:
            if area_name in lowered:
                return area_name
        if room and room.lower() not in lowered:
            return text
        # quando a descrição do local já é específica, preserva o nome do trecho sem repetir o cômodo
        return text

    def _build_visual_object_prompt(self, message: str) -> str:
        obj = self._extract_object_name(message)
        if not obj:
            return ""
        lowered = message.lower()
        room_hint = self._extract_room_hint(message)
        area_hint = self._extract_area_hint(message)
        room_clause = f" O contexto sugerido é o cômodo {room_hint}." if room_hint else ""
        area_clause = f" Também procure em {area_hint}." if area_hint else ""
        return (
            f"[LOCALIZAÇÃO DE OBJETO]\n"
            f"Procure o objeto '{obj}' no ambiente visível. "
            "Se ele estiver na imagem ou na tela, descreva o local exato. "
            "Se não estiver visível, use a memória do ambiente como referência e diga que é a última posição conhecida."
            f"{room_clause}{area_clause}"
        )

    def _build_visual_priority_prompt(self, message: str) -> str:
        if not self._is_object_location_request(message):
            return ""
        return (
            "[VISÃO ATIVA]\n"
            "Use primeiro a visão do ambiente, da câmera ou da tela para confirmar o local. "
            "Considere também áreas semânticas do cômodo, como mesa da direita, prateleira, canto, armário, gaveta. "
            "Somente recorra à memória do ambiente como fallback quando não houver confirmação visual direta."
        )

    def _is_room_inventory_request(self, message: str) -> bool:
        if not message or not message.strip():
            return False
        lowered = message.lower()
        has_inventory = any(token in lowered for token in [
            "o que tem", "o que há", "quais objetos", "quais itens", "qual objeto",
            "me mostra", "me mostre", "existe", "há", "tem algo", "tem algum"
        ])
        if not has_inventory:
            return False
        return self._extract_room_hint(message) is not None or self._extract_area_hint(message) is not None

    def _resolve_room_inventory(self, message: str) -> str | None:
        if not message or not message.strip():
            return None
        if not self._is_room_inventory_request(message):
            return None
        room_hint = self._extract_room_hint(message)
        area_hint = self._extract_area_hint(message)
        rows = self.memory.find_objects_in_room(room=room_hint, area=area_hint, limit=10)
        if not rows:
            return None

        items = []
        for row in rows[:5]:
            obj = row.get('object_name') or 'objeto'
            loc = row.get('location') or 'local desconhecido'
            room_label = row.get('room') or room_hint or 'ambiente'
            area_label = row.get('area') or area_hint or ''
            if area_label and area_label.lower() not in loc.lower():
                items.append(f"- {obj}: {loc} ({area_label})")
            else:
                items.append(f"- {obj}: {loc} ({room_label})")

        room_label = room_hint or area_hint or 'este ambiente'
        return f"No {room_label}, lembro de: " + "; ".join(items) + "."

    def _resolve_object_location(self, message: str) -> str | None:
        if not message or not message.strip():
            return None
        lowered = message.lower()
        if not self._is_object_location_request(message):
            return None
        obj = self._extract_object_name(message)
        room_hint = None
        for room_name in ["quarto", "sala", "cozinha", "banheiro", "escritório", "escritorio", "garagem", "varanda", "prateleira", "mesa"]:
            if room_name in lowered:
                room_hint = room_name
                break
        if obj:
            record = self.memory.find_object_location(obj, room=room_hint)
            if record and record.get("location"):
                room_label = record.get("room") or record.get("area") or room_hint or "ambiente"
                location = record.get("location")
                area_token = record.get("area")
                if area_token and area_token not in location.lower():
                    return f"Última vez que vi o {obj} no {room_label}, em {area_token}, ele estava {location}."
                room_part = f" no {room_label}" if room_label and room_label != "ambiente" else ""
                return f"Última vez que vi o {obj}{room_part}, ele estava {location}."
        for candidate in self.memory.find_related_objects(lowered, limit=5):
            location = candidate.get("location")
            if location:
                room_label = candidate.get("room") or candidate.get("area") or "ambiente"
                if candidate.get("area") and candidate.get("area") not in location.lower():
                    return f"Última vez que vi o {candidate['object_name']} no {room_label}, em {candidate['area']}, ele estava {location}."
                return f"Última vez que vi o {candidate['object_name']} no {room_label}, ele estava {location}."
        return None

    def process(
        self,
        message,
        session_id=None,
        use_screen=False,
        region=None,
        monitor=None,
        camera_image=None,
        doc_id=None,
    ):
        session_id = self.memory.get_or_create_session(session_id)
        auto_visual_context = bool(
            re.search(
                r"\b(?:onde\s+est[aá]|onde\s+fica|localiz\w+|encontre|achar|procure|procura|veja\s+o\s+ambiente|observe\s+o\s+ambiente|me\s+mostre\s+o\s+ambiente|qual\s+(?:objeto|coisa|item)\s+est[aá])\b",
                (message or "").lower(),
                re.IGNORECASE | re.UNICODE,
            )
        )
        effective_use_screen = bool(use_screen or auto_visual_context)

        self._remember_object_from_message(message)
        location_hint = self._resolve_object_location(message)
        room_inventory_hint = self._resolve_room_inventory(message)
        if location_hint and not (camera_image is not None or effective_use_screen):
            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", location_hint)
            return {
                "session_id": session_id,
                "response": location_hint,
                "tools_used": [],
                "evidence": None,
            }
        if room_inventory_hint and not (camera_image is not None or effective_use_screen):
            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", room_inventory_hint)
            return {
                "session_id": session_id,
                "response": room_inventory_hint,
                "tools_used": [],
                "evidence": None,
            }

        tools_used = []
        images = []
        evidence = EvidenceStore()

        # ── Planner: decisões centralizadas ─────────────────────────
        plan = build_plan(
            message,
            use_screen_requested=bool(effective_use_screen),
            camera_image=camera_image is not None,
            requested_doc_id=doc_id,
            session_doc_id=self._session_docs.get(session_id),
        )
        
        # ── Memória Cognitiva: Recuperação ──────────────────────────
        # Componente opcional de personalização; se ausente/indisponível,
        # o chat segue sem lembrar fatos (não deve nunca quebrar a conversa).
        cognitive_memory = getattr(self, "cognitive_memory", None)
        user_facts = cognitive_memory.recall(message) if cognitive_memory else []
        # Guardamos os fatos para injetar no prompt e para a reflexão posterior
        cognitive_context = user_facts if user_facts else []


        # ── Resolução de monitor: plano > parâmetro > default ───────
        effective_monitor = monitor if monitor is not None else 0
        if plan.monitor is not None:
            effective_monitor = plan.monitor

        evidence.add_intent(plan.vision_intent.value, effective_monitor)

        # ── Validação do monitor ────────────────────────────────────
        if plan.capture_screen:
            monitors = ScreenManager.list_monitors()
            if effective_monitor < 0 or effective_monitor >= len(monitors):
                return {
                    "session_id": session_id,
                    "response": (
                        f"Monitor {effective_monitor} não existe. "
                        f"Existem {len(monitors)} monitores (0 a {len(monitors) - 1})."
                    ),
                    "tools_used": [],
                }

        ocr_text = None
        vision_ctx = None
        vision_source = "none"

        # ── Captura de tela via planner ─────────────────────────────
        if plan.capture_screen:
            # Check permissions before attempting capture. If screen/camera
            # permissions are not allowed, return a structured action requesting
            # permission so the frontend can ask the user and resend with an image.
            from ..security.permissions import PermissionManager
            perm = PermissionManager()
            if not perm.is_allowed('camera') and not perm.is_allowed('screen_capture'):
               # return structured response instructing frontend to request camera
               actions = [
                   {
                       "type": "request_permission",
                       "permission": "camera",
                       "reason": "Localizar objeto visualmente",
                       "scope": "one_time",
                       "original_message": message,
                   }
               ]
               return {
                   "session_id": session_id,
                   "response": "Para localizar visualmente este objeto preciso acessar a câmera. Posso pedir sua permissão?",
                   "tools_used": [],
                   "evidence": None,
                   "actions": actions,
               }
            physical_name = None
            try:
               monitors = ScreenManager.list_monitors()
               if 0 <= effective_monitor < len(monitors):
                   physical_name = monitors[effective_monitor].get("name")
            except Exception:
               physical_name = None
            vision_ctx = self._vision_pipeline(
               message=message,
               monitor=effective_monitor,
               region=region,
               intent=plan.vision_intent,
               human_monitor=plan.human_monitor,
               physical_monitor_name=physical_name,
            )
            if not vision_ctx.is_valid:
                log.error("[VISION] pipeline_failed errors=%s", vision_ctx.errors)
                fallback_response = self._resolve_object_location(message)
                if fallback_response and self._is_object_location_request(message):
                    self.memory.add_message(session_id, "user", message)
                    self.memory.add_message(session_id, "assistant", fallback_response)
                    return {
                        "session_id": session_id,
                        "response": fallback_response,
                        "tools_used": [],
                        "evidence": None,
                    }
                return {
                    "session_id": session_id,
                    "response": (
                        "Não consegui capturar ou analisar a tela. "
                        + "; ".join(vision_ctx.errors)
                    ),
                    "tools_used": [],
                }
            vision_source = "screen"
            tools_used.append("screen_capture")
            images.append(vision_ctx.image_bytes)
            ocr_text = vision_ctx.ocr_text
            # ── Evidence tracking ────────────────────────────────
            if vision_ctx.resolution:
                evidence.add_screen(
                    monitor=effective_monitor,
                    width=vision_ctx.resolution[0],
                    height=vision_ctx.resolution[1],
                )
            if vision_ctx.ocr_text:
                evidence.add_ocr(vision_ctx.ocr_text)
            if vision_ctx.window_app:
                evidence.add_window(vision_ctx.window_app, vision_ctx.window_title)

            # Ingestão de detecções estruturadas (se o engine fornecer)
            try:
                detections = None
                if getattr(vision_ctx, "metadata", None):
                    detections = vision_ctx.metadata.get("detections")
                if detections:
                    # gravamos cada detecção estruturada na memória do ambiente
                    for d in detections:
                        try:
                            label = d.get("label") or d.get("name")
                            bbox = d.get("bbox") if isinstance(d.get("bbox"), dict) else None
                            conf = float(d.get("confidence", 0.0))
                            ctx_text = f"detecção estruturada: {label}"
                            # room/area não são conhecidos pelo detector — ficam vazios
                            try:
                            self.memory.reconcile_detection(label, bbox, monitor=effective_monitor, context=ctx_text, confidence=conf)
                            except Exception:
                            log.exception("failed to reconcile detection for %s", label)
                        except Exception:
                            log.exception("failed processing single detection")
            except Exception:
                log.exception("failed ingesting detections from vision_ctx")

        # ── Imagem da câmera (camera_image explícito) ───────────────
        if camera_image is not None:
            vision_source = "camera"
            if isinstance(camera_image, str):
                camera_image = base64.b64decode(camera_image)
            images.append(camera_image)
            tools_used.append("image_input")
            ocr_text = ocr_text or self._safe_ocr_bytes(camera_image)
            log.info("[VISION] camera_image=attached bytes=%d", len(camera_image))

        # ── Montagem da mensagem ────────────────────────────────────
        msg_parts = [message]

        obj_name = self._extract_object_name(message)
        if obj_name and (camera_image is not None or use_screen):
            msg_parts.append(self._build_visual_object_prompt(message))
            visual_priority = self._build_visual_priority_prompt(message)
            if visual_priority:
                msg_parts.append(visual_priority)

        env_memory = self.memory.find_related_objects(message, limit=5)
        if env_memory:
            env_str = "\n".join([f"- {item['object_name']}: {item['location']}" for item in env_memory])
            msg_parts.insert(0, f"[MEMÓRIA DO AMBIENTE]\n{env_str}\n")

        if location_hint:
            msg_parts.insert(0, f"[MEMÓRIA DE LOCALIZAÇÃO]\n{location_hint}\n")

        if cognitive_context:
            facts_str = "\n".join([f"- {f}" for f in cognitive_context])
            msg_parts.insert(0, f"[MEMÓRIA DO ALUNO]\n{facts_str}\n")

        if images and not vision_ctx:
            # ...existing code...

            msg_parts.append(
                build_image_note(
                    camera=(vision_source == "camera"),
                    monitor=effective_monitor if vision_source == "screen" else None,
                    size=None,
                )
            )
            if vision_source == "screen":
                janela = format_window_note(window.active_window())
                if janela:
                    msg_parts.append(janela)
            bloco_ocr = decide_ocr_block(ocr_text)
            if bloco_ocr:
                msg_parts.append(bloco_ocr)

        # ── Documento anexado / lembrado pela sessão ─────────────────
        if plan.wants_document:
            self._require("file_access")
            doc = self.memory.get_document(plan.doc_id)
            if doc:
                from pathlib import Path

                from ..tools.documents import (
                    build_digest,
                    load_document_text,
                    retrieve_relevant,
                )

                _, text = load_document_text(Path(doc["path"]))
                if len(text) <= WHOLE_DOC_MAX_CHARS:
                    body = whole_doc_body(text)
                elif plan.whole_doc:
                    digest = self._digest_cache.get(plan.doc_id)
                    if not digest:
                        digest = build_digest(
                            text, chat_fn=lambda s: chat([{"role": "user", "content": s}])
                        )
                        if len(self._digest_cache) > 6:
                            self._digest_cache.pop(next(iter(self._digest_cache)))
                        self._digest_cache[plan.doc_id] = digest
                    body = digest_body(digest)
                else:
                    trechos = None
                    try:
                        from ..tools import rag

                        trechos = rag.search(plan.doc_id, text, message)
                    except Exception as exc:
                        logging.getLogger("uvicorn.error").warning(
                            "RAG falhou: %s", exc
                        )
                    if not trechos:
                        trechos = retrieve_relevant(message, text)
                    body = excerpts_body(trechos)
                msg_parts.append(
                    build_document_block(doc["name"], doc["pages"], body)
                )
                tools_used.append("document")
                self._session_docs[session_id] = plan.doc_id
                if len(self._session_docs) > 50:
                    self._session_docs.pop(next(iter(self._session_docs)))

        enriched_message = "\n\n".join(msg_parts)

        # Conversa casual (categoria CHAT / saudação, sem doc/visão) usa chat
        # simples sem tool-calling e system prompt de chat limpo, evitando que
        # o modelo ecoe instruções de visão/ferramentas na resposta.
        is_casual = (
            not images
            and not plan.wants_document
            and (is_social_greeting(message) or plan.category.value == "CHAT")
        )

        # ── System prompt: visão, chat ou tutor ────────────────────
        if vision_ctx and vision_ctx.is_valid:
            messages = self.ctx.assemble_vision(session_id, enriched_message, vision_ctx)
        else:
            messages = self.ctx.assemble(
                session_id, enriched_message, chat_mode=is_casual
            )

        # ── Resposta ────────────────────────────────────────────────
        # Fast-path anti-alucinação: saudações/conversa casual vão para chat de
        # texto SIMPLES sem tool-calling. Modelos de tool-calling CONFABULAM
        # "resposta de função JSON" em vez de apenas conversar — por isso
        # evitamos tool-calling sempre que não há intenção real de ferramenta.
        try:
            if is_casual:
                try:
                    response_text = chat(messages)
                except PermissionDeniedError:
                    raise
                except Exception as exc:
                    log.warning("[CHAT] casual_chat_failed: %s", exc)
                    response_text = (
                        "Não consegui processar agora (o modelo parece indisponível). "
                        "Tente novamente em instantes."
                    )
            elif plan.wants_document:
                response_text = self._run_tool_loop(
                    messages, images, tools_used, allow_tools=False
                )
            else:
                response_text = self._run_with_orchestration(
                    messages, images, tools_used, plan
                )
        except PermissionDeniedError:
            raise
        except Exception as exc:
            log.warning("[VISION] fallback_after_chat_error: %s", exc)
            response_text = self._fallback_visual_response(message, location_hint, room_inventory_hint, session_id)

        # ── Validação da resposta (anti-alucinação) ────────────────
        if evidence.has_screen:
            validator = ResponseValidator(evidence)
            issues = validator.validate(response_text)
            if issues:
                log.warning("[VALIDATOR] response_issues=%s", issues)

        # Atualiza memória com observações da resposta do assistente quando a visão estava ativa
        try:
            if vision_source in ("camera", "screen") and response_text:
                self._remember_object_from_assistant(response_text, vision_source)
        except Exception:
            log.exception("falha ao armazenar observação visual na memória")

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", response_text)

        # ── Reflexão Cognitiva: aprende com a interação ────────────────
        # Executamos em background para não atrasar a resposta ao usuário
        import threading
        threading.Thread(
            target=self._reflect_and_remember, 
            args=(message, response_text), 
            daemon=True
        ).start()

        return {
            "session_id": session_id,
            "response": response_text,
            "tools_used": tools_used,
            "evidence": evidence.summary() if evidence else None,
        }

    def _fallback_visual_response(
        self,
        message: str,
        location_hint: str | None,
        room_inventory_hint: str | None,
        session_id: str,
    ) -> str:
        """Fallback robusto quando o modelo de visão não responde."""
        lowered = (message or "").lower()
        if location_hint:
            return location_hint
        if room_inventory_hint:
            return room_inventory_hint
        if any(token in lowered for token in ["o que você vê", "o que ve", "quais objetos", "o que tem", "o que há", "o que ha", "descreva a imagem", "descreva a foto"]):
            return (
                "Não consegui analisar a imagem recebida no momento, mas posso tentar pela memória do ambiente "
                "ou pela próxima captura. Se quiser, repita a pergunta ou envie uma imagem mais clara."
            )
        return "Não consegui analisar a imagem recebida no momento. Tente novamente em instantes."

    def _reflect_and_remember(self, message: str, response: str) -> None:
        """Aprende com a interação em segundo plano (memória cognitiva épisódica).

        Extrai fatos declarativos simples do que o aluno escreveu (heurística,
        barato e sem bloquear) e os salva via CognitiveMemory. Nunca deve lançar
        exceção — roda em thread daemon.
        """
        try:
            if not message or not message.strip():
                return
            cognitive_memory = getattr(self, "cognitive_memory", None)
            if cognitive_memory is None:
                return
            for chunk in self._candidate_facts(message):
                try:
                    cognitive_memory.remember(chunk)
                except Exception:
                    continue
        except Exception as exc:
            log.warning("[COGNITIVE] reflect_failed: %s", exc)

    def _candidate_facts(self, message: str) -> list[str]:
        """Pequena extração heurística de fatos sobre o aluno."""
        patterns = [
            "eu prefiro", "eu gosto", "eu adoro", "eu odeio", "eu detesto",
            "meu nome é", "eu sou", "meu curso", "minha escola", "eu estudo",
            "estou estudando", "preciso de ajuda com", "estou com dificuldade",
            "tenho prova", "minha prova", "meu professor", "minha matéria",
        ]
        lowered = message.lower()
        facts: list[str] = []
        for punct in (".", "!", "?"):
            for seg in message.split(punct):
                seg_low = seg.lower().strip()
                for p in patterns:
                    if p in seg_low and len(seg.strip()) > 3:
                        facts.append(seg.strip()[:220])
                        break
        return facts[:6]

    def _remember_object_from_assistant(self, assistant_text: str, vision_source: str = "camera") -> None:
        """Tenta extrair frases de localização da resposta do assistente e grava na memória.

        Procura frases simples do tipo "o <objeto> está <local>" ou "vejo <objeto> em <local>".
        Usa confiança alta (0.95) quando a origem foi visão (camera/screen).
        """
        try:
            if not assistant_text or not assistant_text.strip():
                return
            text = assistant_text.strip()
            lowered = text.lower()
            import re as _re
            objs = [
                "celular", "telefone", "chave", "mochila", "livro", "caderno",
                "carregador", "mouse", "teclado", "notebook", "agenda", "fone",
                "relógio", "garrafa", "caneta", "laptop"
            ]
            for obj in objs:
                patterns = [
                    rf"(?:vejo|encontrei|encontra-se|está|esta|o|a|um|uma)?\s*{_re.escape(obj)}\s*(?:está|esta|em|na|no|sobre|no canto|na mesa|na prateleira)?\s*(.+?)(?:[.!?]|$)",
                    rf"(?:{_re.escape(obj)})\s*(?:está|esta|em|na|no|sobre)\s*(.+?)(?:[.!?]|$)",
                ]
                for pattern in patterns:
                    m = _re.search(pattern, lowered)
                    if m:
                        loc = m.group(1).strip()
                        if len(loc) > 1 and len(loc) < 180 and not any(token in loc for token in ["não", "nao", "não vejo", "nao vejo"]):
                            room_hint = self._extract_room_hint(text)
                            semantic_area = self._extract_semantic_area(loc, room_hint)
                            confidence = 0.95 if vision_source in ("camera", "screen") else 0.6
                            try:
                                self.memory.remember_object_location(obj, loc, room=room_hint, area=semantic_area or room_hint or loc, context=f"observado pelo agente: {text}", confidence=confidence)
                            except Exception:
                                log.exception("falha ao gravar observação visual")
                            finally:
                                return
        except Exception:
            log.exception("_remember_object_from_assistant falhou")
        return

    def _run_tool_loop(self, messages, images, tools_used, allow_tools=True):
        """Agent Loop V2: retry + circuit breaker + evidence por step.

        Fluxo:
        1. Se images → caminho de visão (1 chamada LLM com imagem)
        2. Se !allow_tools → chat direto
        3. Loop de tool calling com:
           - Retry com backoff exponencial por tool
           - Circuit breaker por tool (3 falhas → open → 60s recovery)
           - Max 5 iterações (anti-loop)
           - Structured logging com duration_ms
        """
        if images:
            total_bytes = sum(len(img) for img in images if isinstance(img, bytes))
            log.info("[VISION] sending_images=%d total_bytes=%d message_count=%d",
                     len(images), total_bytes, len(messages))
            if total_bytes <= 0:
                raise RuntimeError("Nenhuma imagem válida para análise visual.")
            response = chat(messages, images=images)
            if not response or not response.strip():
                raise RuntimeError("O modelo de visão não retornou resposta.")
            log.info("[VISION] vision_response=length=%d", len(response))
            return response
        if not allow_tools:
            return chat(messages)

        from ..core.orchestrator.circuit_breaker import CircuitBreaker
        from .llm import synthesize

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        # Circuit breakers por tool (independentes)
        tool_cbs: dict[str, CircuitBreaker] = {}
        MAX_STEPS = 5
        MAX_RETRIES_PER_TOOL = 2
        BACKOFF_BASE_MS = 200.0

        current = list(messages)
        for step in range(MAX_STEPS):
            try:
                reply = chat_with_tools(current, all_schemas())
            except Exception as exc:
                log.warning("[LOOP] step=%d chat_with_tools failed: %s — fallback", step, exc)
                return chat(current)

            if not reply["tool_calls"]:
                # Nenhuma tool chamada: obter resposta limpa via chat simples.
                # O `content` do chamada tool-trainada pode ser lixo
                # ("Não há resposta JSON necessária..."), então preferimos
                # gerar novamente sem o contexto de tool-calling.
                return chat(current)

            current.append(
                {"role": "assistant", "content": reply["content"], "tool_calls": reply["tool_calls"]}
            )

            for call in reply["tool_calls"]:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                entry = get(name)

                if not entry:
                    result = f"Ferramenta desconhecida: {name}"
                    log.warning("[LOOP] step=%d unknown_tool=%s", step, name)
                    current.append({"role": "tool", "name": name, "content": result})
                    continue

                # Circuit breaker por tool
                if name not in tool_cbs:
                    tool_cbs[name] = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
                cb = tool_cbs[name]

                if not cb.allow():
                    result = f"Ferramenta {name} temporariamente indisponível (circuit open)"
                    log.warning("[LOOP] step=%d tool=%s circuit_open", step, name)
                    current.append({"role": "tool", "name": name, "content": result})
                    continue

                # Retry com backoff exponencial
                last_error = None
                for attempt in range(MAX_RETRIES_PER_TOOL + 1):
                    try:
                        if entry.permission:
                            self._require(entry.permission)
                        import time as _time
                        t0 = _time.time()
                        result = entry.handler(args)
                        duration_ms = (_time.time() - t0) * 1000
                        entry.stats.record_success(duration_ms)
                        cb.record_success()
                        log.info("[LOOP] step=%d tool=%s attempt=%d success duration_ms=%.1f",
                                 step, name, attempt + 1, duration_ms)
                        break
                    except PermissionDeniedError as exc:
                        result = f"Permissão negada para {name}: {exc}"
                        entry.stats.record_failure(str(exc), 0.0)
                        cb.record_failure()
                        log.warning("[LOOP] step=%d tool=%s permission_denied", step, name)
                        break
                    except Exception as exc:
                        last_error = exc
                        entry.stats.record_failure(str(exc), 0.0)
                        if attempt < MAX_RETRIES_PER_TOOL:
                            delay_ms = BACKOFF_BASE_MS * (2 ** attempt)
                            log.warning("[LOOP] step=%d tool=%s attempt=%d failed: %s retry_ms=%.0f",
                                         step, name, attempt + 1, exc, delay_ms)
                            import time as _time
                            _time.sleep(delay_ms / 1000)
                        else:
                            cb.record_failure()
                            result = f"Falha ao executar {name} após {MAX_RETRIES_PER_TOOL + 1} tentativas: {last_error}"
                            log.error("[LOOP] step=%d tool=%s exhausted: %s", step, name, last_error)

                tools_used.append(name)

                # Síntese para web_search com resultados longos
                if name == "web_search" and "---" in result:
                    try:
                        return synthesize(last_user, result)
                    except Exception as exc:
                        log.warning("[LOOP] synthesize failed: %s", exc)

                current.append({"role": "tool", "name": name, "content": result})

        log.warning("[LOOP] max_steps=%d reached", MAX_STEPS)
        return reply.get("content") or ""

    def _run_with_orchestration(self, messages, images, tools_used, plan):
        """Caminho de orquestração: uma pergunta vira um plano multi-step.

        Usa o AgentOrchestrator/ToolExecutor (plano de execução com grafo de
        dependências, retry/timeout por política e evidências) para distribuir
        VÁRIAS ações encadeadas dentro de uma única resposta. Se nenhuma
        ferramenta for necessária ou o plano for inválido, cai no loop
        reativo tradicional (_run_tool_loop).
        """
        from ..core.orchestrator.execution_plan import ExecutionPlan
        from ..core.orchestrator.executor import ToolExecutor
        from ..core.orchestrator.orchestrator import AgentOrchestrator
        from ..core.plan_builder import build_plan as build_tool_plan

        # Caminho de visão / sem tools fica no loop tradicional
        if images or (hasattr(plan, "category") and plan.category.value == "CHAT"):
            return self._run_tool_loop(messages, images, tools_used)

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        # ── 1. Gera o plano (JSON) de ações ────────────────────────
        build = build_tool_plan(
            last_user,
            llm_fn=lambda prompt: chat([{"role": "user", "content": prompt}]),
        )
        if not build.ok:
            return self._run_tool_loop(messages, images, tools_used)

        from ..core.tool_registry import get as registry_get

        orch = AgentOrchestrator()
        orch.set_permission_fn(lambda tool_name: self._tool_allowed(tool_name))

        # ── 2. Monta ExecutionPlan com grafo de dependências ───────
        execution = ExecutionPlan(goal=last_user, intent=plan.category.value)
        id_by_index: dict[int, str] = {}
        for idx, pstep in enumerate(build.steps):
            dep_ids = [id_by_index[int(dep)] for dep in pstep.depends_on if dep.isdigit()]
            step = execution.add_step(
                tool=pstep.tool,
                arguments=pstep.arguments,
                depends_on=dep_ids,
                required=pstep.required,
            )
            id_by_index[idx] = step.id

        ctx = orch.create_context(last_user, session_id="")
        ctx.plan = execution

        # ── 3. Registra handlers (adapter dict -> kwargs) ─────────
        for pstep in build.steps:
            entry = registry_get(pstep.tool)
            if entry:
                orch.register_tool(
                    pstep.tool,
                    lambda _e=entry, **kw: _e.handler(kw),
                )

        # ── 4. Executa o plano ─────────────────────────────────────
        try:
            orch.execute(ctx)
        except PermissionDeniedError as exc:
            log.warning("[ORCH] permission_denied=%s", exc)
            return {
                "response": f"Permissão negada para executar essa ação: {exc}",
                "tools_used": list(tools_used),
            }

        for step in execution.steps:
            if step.status.value in ("SUCCESS", "FAILED") and step.tool not in tools_used:
                tools_used.append(step.tool)

        # ── 5. Síntese da resposta final ───────────────────────────
        blocks = []
        success = False
        for step in execution.steps:
            if step.status.value == "SUCCESS":
                success = True
                blocks.append(f"[{step.tool}] {step.result}")
        if not success:
            return self._run_tool_loop(messages, images, tools_used)

        final_prompt = (
            f"Pergunta do usuário: {last_user}\n\n"
            "Resultados das ações executadas:\n" + "\n\n".join(blocks) +
            "\n\nResponda em português com base exclusivamente nos resultados "
            "acima. Se algo ficou sem resposta ou vago, diga claramente que "
            "não encontrou. Não invente informações."
        )
        response_text = chat([{"role": "user", "content": final_prompt}])
        log.info("[ORCH] steps=%d tools=%s exec_id=%s",
                 len(execution.steps), tools_used, ctx.execution_id)
        return response_text

    def _tool_allowed(self, tool_name: str) -> bool:
        """Verifica permissão de uma ferramenta (por nome no registry)."""
        from ..core.tool_registry import get as registry_get

        entry = registry_get(tool_name)
        if not entry or not entry.permission:
            return True
        try:
            self._require(entry.permission)
            return True
        except PermissionDeniedError:
            return False

    def _vision_pipeline(
        self,
        message: str,
        monitor: int,
        region,
        intent: VisionIntent,
        *,
        human_monitor: int | None = None,
        physical_monitor_name: str | None = None,
    ) -> VisionContext:
        """Pipeline dedicado de visão: captura → processa → contexto."""
        stages = []
        errors = []

        # ── CAPTURE ─────────────────────────────────────────────────
        self._require("screen_capture")
        log.info("[VISION] stage=CAPTURE_REQUESTED monitor=%s", monitor)
        stages.append("CAPTURE_REQUESTED")

        try:
            shot = ScreenManager.capture_monitor(monitor_id=monitor, region=region)
        except Exception as exc:
            errors.append(f"Falha na captura: {exc}")
            log.error("[VISION] stage=CAPTURE_FAILED error=%s", exc)
            return VisionContext(source="screen", monitor_id=monitor, errors=errors)

        capture_res = screen.validate_capture(shot, monitor)
        if not capture_res.is_valid:
            errors.append(capture_res.error or "Captura inválida")
            log.error("[VISION] stage=CAPTURE_INVALID error=%s", capture_res.error)
            return VisionContext(source="screen", monitor_id=monitor, errors=errors)

        stages.append("CAPTURED")
        log.info("[VISION] stage=CAPTURED resolution=%dx%d monitor=%s",
                 capture_res.width, capture_res.height, monitor)

        # ── WINDOW ──────────────────────────────────────────────────
        window_info = None
        try:
            window_info = window.active_window()
        except Exception:
            pass

        # ── PROCESS (OCR + context) ─────────────────────────────────
        ctx = process_capture(
            shot, monitor, window_info,
            user_question=message,
            intent=intent,
        )
        ctx.errors.extend(errors)

        # ── ENRIQUECIMENTO V3 — metadados de monitor ───────────────
        if human_monitor is not None:
            ctx.human_monitor = human_monitor
        if physical_monitor_name:
            ctx.physical_monitor_name = physical_monitor_name
        try:
            mon_info = ScreenManager.get_monitor(monitor)
            if mon_info:
                ctx.position = {
                    "left": mon_info.get("left", 0),
                    "top": mon_info.get("top", 0),
                    "width": mon_info.get("width", 0),
                    "height": mon_info.get("height", 0),
                    "index": mon_info.get("index", monitor),
                }
        except Exception:
            pass
        return ctx

    @staticmethod
    def _safe_ocr(pil_image):
        if not ocr.available():
            return None
        try:
            return ocr.read_text(pil_image)
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("OCR falhou: %s", exc)
            return None

    @staticmethod
    def _safe_ocr_bytes(data):
        from io import BytesIO

        from PIL import Image

        try:
            return StudyAgent._safe_ocr(Image.open(BytesIO(data)))
        except Exception:
            return None

    def capture_and_read_screen(self, region=None, monitor=1):
        self._require("screen_capture")
        shot = ScreenManager.capture_monitor(monitor_id=monitor, region=region)
        result = {"ocr_available": ocr.available()}
        if ocr.available():
            try:
                result["text"] = ocr.read_text(shot)
            except Exception as exc:
                result["text"] = ""
                result["ocr_error"] = str(exc)
        else:
            result["text"] = ""
        return shot, result

    def analyze_screen(self, question, session_id=None, region=None, monitor=1):
        """Captura tela via fluxo visual completo (use_screen=True → planner → vision pipeline)."""
        prompt = question or (
            "Analise esta captura de tela. Identifique o conteúdo visível e responda "
            "com base exclusivamente no que estiver na tela."
        )
        return self.process(
            prompt,
            session_id=session_id,
            use_screen=True,
            region=region,
            monitor=monitor,
        )

    def status(self):
        return {
            "models": available_models(),
            "ocr_available": ocr.available(),
        }

    @staticmethod
    def _require(name):
        from ..security.permissions import PermissionManager

        PermissionManager().require(name)


__all__ = ["StudyAgent", "PermissionDeniedError"]
