"""Core V2 do StudyAgent: núcleo de orquestração.

Módulos:
- model_manager: seleção de modelos por função (texto, visão, síntese…)
- planner: roteamento de intenções (tela/documento/monitor) antes do LLM
- tool_registry: registro central de ferramentas + schemas
- registered_tools: ferramentas padrão (busca, url, calculadora)
"""
