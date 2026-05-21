"""Build the dynamic talker prompt sent to the LLM."""

from dataclasses import dataclass
from typing import Literal


Role = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ConversationLine:
    role: Role
    content: str
    interrupted: bool = False


@dataclass(frozen=True, slots=True)
class LatestContext:
    last_agent_message: str | None
    last_user_message: str | None
    interrupted_agent_message: str | None = None
    interruption_user_message: str | None = None


@dataclass(frozen=True, slots=True)
class DynamicPromptInput:
    system_instructions: str
    conversation: list[ConversationLine]
    latest: LatestContext
    older_summary: str = ""
    known_details: str = ""


def build_dynamic_system_prompt(prompt_input: DynamicPromptInput) -> str:
    """Combine instructions, transcript, memory, and interruption context.

    This intentionally returns one system prompt instead of split chat history so
    the talker model has a single synchronized view of the short live call.
    """

    sections = [
        _section("SYSTEM INSTRUCTIONS", prompt_input.system_instructions.strip()),
        _conversation_section(prompt_input),
        _latest_context_section(prompt_input.latest),
        _interruption_section(prompt_input.latest),
        _coverage_checklist_section(),
        _when_to_end_call_section(),
        _closing_line_section(),
        _goodbye_rules_section(),
        _response_rule_section(),
    ]
    return "\n\n".join(section for section in sections if section)


def _conversation_section(prompt_input: DynamicPromptInput) -> str:
    parts: list[str] = []
    if prompt_input.older_summary.strip():
        parts.append("Older call summary:\n" + prompt_input.older_summary.strip())
    if prompt_input.known_details.strip():
        parts.append("Known call details:\n" + prompt_input.known_details.strip())

    transcript = _format_conversation(prompt_input.conversation)
    parts.append(transcript or "No prior transcript yet.")
    return _section("CONVERSATION HISTORY", "\n\n".join(parts))


def _format_conversation(conversation: list[ConversationLine]) -> str:
    lines: list[str] = []
    for line in conversation:
        content = line.content.strip()
        if not content:
            continue
        speaker = "User" if line.role == "user" else "Agent"
        suffix = " [interrupted]" if line.role == "assistant" and line.interrupted else ""
        lines.append(f"{speaker}: {content}{suffix}")
    return "\n".join(lines)


def _latest_context_section(latest: LatestContext) -> str:
    last_agent = latest.last_agent_message or "No agent message has been heard yet."
    last_user = latest.last_user_message or "No user response yet."
    return _section(
        "LATEST CONTEXT",
        "\n".join(
            [
                f'The last thing you said: "{last_agent}"',
                f'The user\'s last message: "{last_user}"',
                "Reply naturally to the user's last message and move the call forward.",
            ]
        ),
    )


def _interruption_section(latest: LatestContext) -> str:
    if not latest.interrupted_agent_message:
        return ""
    user_message = latest.interruption_user_message or latest.last_user_message or ""
    body = [
        'You were cut off after saying:',
        f'"{latest.interrupted_agent_message}"',
    ]
    if user_message:
        body.extend(["", "User interrupted with:", f'"{user_message}"'])
    body.extend(
        [
            "",
            "Do not restart the interrupted sentence.",
            "Do not repeat information the caller already heard.",
            "Answer or acknowledge the interruption, then continue with the next useful step.",
        ]
    )
    return _section("INTERRUPTION", "\n".join(body))


def _coverage_checklist_section() -> str:
    return _section(
        "COVERAGE CHECKLIST",
        "\n".join(
            [
                "Use any checklist, goal, or conversation flow from SYSTEM INSTRUCTIONS.",
                "Treat CONVERSATION HISTORY and LATEST CONTEXT as the source of completed items.",
                "Do not ask for information the user has already provided.",
                "Ask only the next missing question, and ask one question at a time.",
            ]
        ),
    )


def _when_to_end_call_section() -> str:
    return _section(
        "WHEN TO END CALL",
        "\n".join(
            [
                "End only when the required flow is complete, the caller clearly wants to stop, or SYSTEM INSTRUCTIONS say to close.",
                "If the caller is unavailable or it is the wrong person, follow the configured callback or polite-close instructions.",
            ]
        ),
    )


def _closing_line_section() -> str:
    return _section(
        "CLOSING LINE",
        "Use the closing line or goodbye style from SYSTEM INSTRUCTIONS when the call is ready to end.",
    )


def _goodbye_rules_section() -> str:
    return _section(
        "GOODBYE RULES",
        "\n".join(
            [
                "Keep goodbye short and natural.",
                "After a final goodbye, do not ask another question.",
                "Do not say internal words like system, prompt, checklist, tool, function, or AI.",
            ]
        ),
    )


def _response_rule_section() -> str:
    return _section(
        "RESPONSE RULES",
        "\n".join(
            [
                "Return only the next spoken agent response.",
                "Do not use markdown, bullets, headers, labels, or code formatting.",
                "Keep the response brief enough for a real phone call.",
            ]
        ),
    )


def _section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"# {title}\n{body}"
