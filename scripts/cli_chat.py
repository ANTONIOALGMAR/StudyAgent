import sys

sys.path.insert(0, "backend")

from app.agent.agent import StudyAgent


def main():
    agent = StudyAgent()
    session_id = None
    print("StudyAgent CLI — digite 'sair' para encerrar")
    print("Use '!tela sua pergunta' para o agente olhar a tela\n")

    while True:
        try:
            user_input = input("\nvocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("sair", "exit", "quit"):
            print("Até logo!")
            break

        if user_input.startswith("!tela"):
            question = user_input[5:].strip() or None
            result = agent.analyze_screen(question, session_id=session_id)
        else:
            result = agent.process(user_input, session_id=session_id)

        session_id = result["session_id"]
        tools = ", ".join(result["tools_used"]) if result["tools_used"] else "-"
        print(f"\n[{tools}] study: {result['response']}")


if __name__ == "__main__":
    main()
