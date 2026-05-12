"""Claude AI client — Phase 4.

Handles:
- Streaming responses via async generator (SSE format).
- Web search tool use (SerpAPI) with graceful fallback.
- ChromaDB memory: relevant past turns injected into system prompt.
- Conversation turn storage after each response.
- Graceful no-key and API-error messages.
- Expression classification for avatar selection.
"""

import json
import logging
from typing import AsyncIterator

log = logging.getLogger(__name__)

MODEL      = "claude-sonnet-4-6"
MAX_TOKENS = 2048


# ── SSE helper ─────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── System prompt ──────────────────────────────────────────────────────────

def build_system_prompt(memory_context: str = "") -> str:
    from backend.settings_store import get_setting
    from backend.time_utils import now_in

    user_name      = get_setting("user_name",      "Boss")
    timezone       = get_setting("timezone",       "Asia/Kolkata")
    work_start     = get_setting("work_start",     "09:00")
    work_end       = get_setting("work_end",       "19:00")
    greeting_style = get_setting("greeting_style", "casual")

    now      = now_in(timezone)
    time_str = now.strftime("%A, %d %B %Y, %I:%M %p") + " IST"

    prompt = f"""You are AuraBot, the AI chief-of-staff for {user_name}.

PERSONALITY:
- Warm, sharp, professional. Lightly witty when appropriate. Never chirpy or sycophantic.
- Think trusted chief-of-staff who genuinely respects {user_name}'s time and intelligence.
- Address her as {user_name} occasionally — not every message.
- Indian English-friendly: you know IST, Bengaluru context. No need to explain "lakh", "crore", "chai", etc.
- Greeting style preference: {greeting_style}.
- Keep responses concise unless she asks for detail. Bullet points over long paragraphs when practical.

CURRENT CONTEXT:
- Date and time: {time_str}
- Working hours: {work_start}-{work_end} IST

TOOLS:
- web_search: Use proactively for current events, news, prices, or anything outdated. Always cite the source URL.
- check_email / get_priority_email: Read inbox or priority emails. After showing emails, offer to mark as read, star, or archive them.
- label_email: Mark emails read, star, archive, or flag as important. Use after check_email when the user wants to act on a message.
- check_calendar: Read upcoming events.
- create_calendar_event: Schedule meetings or events on Google Calendar. Confirm title, date/time, and duration with the user before creating. Default meeting duration is 1 hour unless specified.
- set_reminder: Set an in-app reminder nudge (does NOT create a calendar event — use create_calendar_event for that).

If asked to do something outside your capabilities, say so clearly and suggest what she can do instead. Be direct and respect her time."""

    if memory_context:
        prompt += f"\n\nRELEVANT MEMORY (past conversations — use naturally when helpful, do not recite verbatim):\n{memory_context}"

    return prompt


# ── Tool definitions ───────────────────────────────────────────────────────

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current, up-to-date information. "
        "Use for recent news, current events, prices, live data, "
        "or anything that may have changed since your training cutoff."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific for better results.",
            }
        },
        "required": ["query"],
    },
}

SET_REMINDER_TOOL = {
    "name": "set_reminder",
    "description": (
        "Set a reminder for the user at a specific date and time. "
        "Use when the user says 'remind me to...', 'set a reminder for...', or similar. "
        "The reminder will appear as a nudge notification at the specified time."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "What to remind the user about.",
            },
            "when": {
                "type": "string",
                "description": (
                    "Absolute ISO 8601 datetime with timezone offset "
                    "(e.g. '2026-05-09T15:00:00+05:30'). "
                    "Convert any relative time (e.g. '3pm', 'in 2 hours', 'tomorrow 9am') "
                    "to an absolute datetime using the current date/time from the system context."
                ),
            },
        },
        "required": ["text", "when"],
    },
}

CHECK_CALENDAR_TOOL = {
    "name": "check_calendar",
    "description": (
        "Read the user's upcoming Google Calendar events. Use when the user asks about "
        "their schedule, meetings, calendar, or upcoming events. Returns events with "
        "title, date/time, and location."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "string",
                "description": "Optional: number of events to fetch (default 10).",
            }
        },
        "required": [],
    },
}

CHECK_WHATSAPP_TOOL = {
    "name": "check_whatsapp",
    "description": (
        "Read the user's recent WhatsApp conversations. Use when the user asks about "
        "WhatsApp messages, chats, or anything WhatsApp-related. Returns recent chats "
        "with names, unread counts, and last message previews."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Optional: 'unread' to focus on unread chats, or leave empty for all recent.",
            }
        },
        "required": [],
    },
}

CHECK_EMAIL_TOOL = {
    "name": "check_email",
    "description": (
        "Read the user's unread Gmail inbox. Use when the user asks about emails, "
        "inbox, messages, or anything mail-related. Returns a list of recent unread "
        "emails with sender, subject, date, and preview snippet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Optional hint: 'unread' (default) or leave empty.",
            }
        },
        "required": [],
    },
}

GET_PRIORITY_EMAIL_TOOL = {
    "name": "get_priority_email",
    "description": (
        "Fetch the user's priority/important Gmail emails. Use when the user asks "
        "about important emails, anything urgent, starred messages, or priority inbox."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "max": {
                "type": "integer",
                "description": "Max number of priority emails to return (default 10).",
            }
        },
        "required": [],
    },
}

LABEL_EMAIL_TOOL = {
    "name": "label_email",
    "description": (
        "Manage a Gmail message — mark as read, star/unstar, archive, or mark as important. "
        "Use when the user says 'mark that as read', 'star this email', 'archive it', "
        "'mark as important', etc. Requires the message_id from a previous check_email result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "The Gmail message ID from a previous email listing.",
            },
            "action": {
                "type": "string",
                "enum": ["mark_read", "star", "unstar", "archive", "important", "not_important"],
                "description": "The action to perform on the message.",
            },
        },
        "required": ["message_id", "action"],
    },
}

CREATE_CALENDAR_EVENT_TOOL = {
    "name": "create_calendar_event",
    "description": (
        "Create an event on the user's Google Calendar. Use when the user asks to "
        "schedule a meeting, add an event, book a slot, or set a calendar reminder. "
        "Always confirm the details before creating."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Event title / meeting name.",
            },
            "start": {
                "type": "string",
                "description": "Start datetime in ISO 8601 with timezone, e.g. '2026-05-13T10:00:00+05:30'.",
            },
            "end": {
                "type": "string",
                "description": "End datetime in ISO 8601 with timezone, e.g. '2026-05-13T11:00:00+05:30'.",
            },
            "description": {
                "type": "string",
                "description": "Optional event description or agenda.",
            },
            "location": {
                "type": "string",
                "description": "Optional location or meeting link.",
            },
        },
        "required": ["summary", "start", "end"],
    },
}


def _build_tools() -> list:
    """Return the tools list for this call — only includes integration tools when connected."""
    tools = [WEB_SEARCH_TOOL, SET_REMINDER_TOOL]
    try:
        from backend.integrations.gmail import get_status as gmail_status
        if gmail_status()["connected"]:
            tools.append(CHECK_EMAIL_TOOL)
            tools.append(GET_PRIORITY_EMAIL_TOOL)
            tools.append(LABEL_EMAIL_TOOL)
    except Exception:
        pass
    try:
        from backend.integrations.calendar import get_status as cal_status
        if cal_status()["connected"]:
            tools.append(CHECK_CALENDAR_TOOL)
            tools.append(CREATE_CALENDAR_EVENT_TOOL)
    except Exception:
        pass
    try:
        from backend.integrations.whatsapp import get_status as wa_status
        if wa_status()["connected"]:
            tools.append(CHECK_WHATSAPP_TOOL)
    except Exception:
        pass
    return tools


# ── Expression classifier ──────────────────────────────────────────────────

def classify_expression(text: str) -> str:
    """Heuristic expression classifier. Phase 4 upgrades this with Claude scoring."""
    t = text.lower()
    if any(w in t for w in ["congratul", "well done", "fantastic", "amazing", "great job", "proud of"]):
        return "celebrating"
    if any(w in t for w in ["sorry to hear", "i understand", "that sounds difficult", "tough time", "hard time"]):
        return "empathetic"
    if any(w in t for w in ["great news", "wonderful", "love it", "brilliant", "exciting"]):
        return "excited"
    if any(w in t for w in ["not sure", "unclear", "i don't know", "uncertain", "hmm", "can't determine"]):
        return "confused"
    if any(w in t for w in ["let me check", "searching", "looking up", "analyzing", "working on", "focusing"]):
        return "focused"
    exclamation_count = text.count("!")
    if exclamation_count >= 2:
        return "happy"
    return "idle"


# ── Main streaming function ────────────────────────────────────────────────

async def stream_claude_response(message: str) -> AsyncIterator[str]:
    """
    Async generator yielding SSE-formatted strings.
    Consumed by FastAPI's StreamingResponse in the /chat endpoint.

    SSE event types emitted:
      {"type": "chunk",       "text": "..."}          — streaming text fragment
      {"type": "tool_start",  "tool": "web_search", "query": "..."} — searching
      {"type": "tool_done",   "tool": "web_search"}   — search complete
      {"type": "error_replace","text": "..."}         — replace any streamed text with error
      {"type": "done",        "expression": "idle"}   — stream complete, pick avatar
    """
    import anthropic
    from backend.secure_store import get_secret

    api_key = get_secret("anthropic_key")
    if not api_key:
        yield _sse({"type": "chunk", "text": (
            "Please add your Anthropic API key in ⚙ Settings → API Keys "
            "to enable AI responses. I'm fully ready once you do!"
        )})
        yield _sse({"type": "done", "expression": "confused"})
        return

    # ── Retrieve relevant memory ───────────────────────────────────────────
    memory_context = ""
    try:
        from backend.memory_store import query_similar, get_stats
        stats = get_stats()
        if stats.get("count", 0) > 0:
            similar = query_similar(message, n_results=5)
            if similar:
                lines = []
                for m in similar:
                    meta      = m.get("metadata", {})
                    date      = meta.get("date", "?")
                    user_text = meta.get("user", "")[:150].replace("\n", " ")
                    bot_text  = meta.get("bot",  "")[:200].replace("\n", " ")
                    lines.append(f"- [{date}] User: {user_text!r} -> AuraBot: {bot_text!r}")
                memory_context = "\n".join(lines)
    except Exception as mem_exc:
        log.debug("Memory query skipped: %s", mem_exc)

    client     = anthropic.AsyncAnthropic(api_key=api_key)
    system     = build_system_prompt(memory_context)
    messages   = [{"role": "user", "content": message}]
    full_text  = ""

    try:
        # ── First streaming call (may trigger tool use) ────────────────────
        tool_calls_made: list[dict] = []
        current_tool: dict | None   = None

        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=_build_tools(),
        ) as stream:

            async for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool = {
                            "id":        block.id,
                            "name":      block.name,
                            "input_str": "",
                        }

                elif etype == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text") and delta.text:
                        full_text += delta.text
                        yield _sse({"type": "chunk", "text": delta.text})
                    elif hasattr(delta, "partial_json") and delta.partial_json and current_tool:
                        current_tool["input_str"] += delta.partial_json

                elif etype == "content_block_stop":
                    if current_tool:
                        try:
                            current_tool["input"] = json.loads(current_tool.get("input_str") or "{}")
                        except json.JSONDecodeError:
                            current_tool["input"] = {}
                        tool_calls_made.append(current_tool)
                        current_tool = None

            first_response = await stream.get_final_message()

        # ── Tool execution + second call ───────────────────────────────────
        if tool_calls_made:
            from backend.integrations.web_search import execute_search
            from backend.integrations.gmail      import execute_email_check

            tool_result_content = []
            for tc in tool_calls_made:
                tool_name = tc.get("name", "")

                if tool_name == "set_reminder":
                    from backend.reminder_store import execute_reminder_set
                    result = await execute_reminder_set(tc["input"])

                elif tool_name == "web_search":
                    query = tc["input"].get("query", "")
                    yield _sse({"type": "tool_start", "tool": "web_search", "query": query})
                    result = await execute_search(query)
                    yield _sse({"type": "tool_done", "tool": "web_search"})

                elif tool_name == "check_email":
                    yield _sse({"type": "tool_start", "tool": "check_email", "query": "Reading inbox..."})
                    result = await execute_email_check(tc["input"])
                    yield _sse({"type": "tool_done", "tool": "check_email"})

                elif tool_name == "get_priority_email":
                    yield _sse({"type": "tool_start", "tool": "get_priority_email", "query": "Reading priority inbox..."})
                    from backend.integrations.gmail import fetch_priority, format_emails_for_claude
                    emails = fetch_priority(tc["input"].get("max", 10))
                    result = format_emails_for_claude(emails) if emails else "No priority emails found."
                    yield _sse({"type": "tool_done", "tool": "get_priority_email"})

                elif tool_name == "label_email":
                    yield _sse({"type": "tool_start", "tool": "label_email", "query": "Updating email..."})
                    from backend.integrations.gmail import apply_label
                    r = apply_label(tc["input"]["message_id"], tc["input"]["action"])
                    result = "Done." if r.get("ok") else f"Failed: {r.get('error')}"
                    yield _sse({"type": "tool_done", "tool": "label_email"})

                elif tool_name == "check_calendar":
                    yield _sse({"type": "tool_start", "tool": "check_calendar", "query": "Reading calendar..."})
                    from backend.integrations.calendar import execute_calendar_check
                    result = await execute_calendar_check(tc["input"])
                    yield _sse({"type": "tool_done", "tool": "check_calendar"})

                elif tool_name == "create_calendar_event":
                    yield _sse({"type": "tool_start", "tool": "create_calendar_event", "query": "Creating event..."})
                    from backend.integrations.calendar import create_event
                    r = create_event(
                        summary     = tc["input"]["summary"],
                        start       = tc["input"]["start"],
                        end         = tc["input"]["end"],
                        description = tc["input"].get("description", ""),
                        location    = tc["input"].get("location", ""),
                    )
                    if r.get("ok"):
                        result = f"Event created: '{r['summary']}'. View it here: {r['link']}"
                    else:
                        result = f"Failed to create event: {r.get('error')}"
                    yield _sse({"type": "tool_done", "tool": "create_calendar_event"})

                elif tool_name == "check_whatsapp":
                    yield _sse({"type": "tool_start", "tool": "check_whatsapp", "query": "Reading WhatsApp chats..."})
                    from backend.integrations.whatsapp import execute_whatsapp_check
                    result = await execute_whatsapp_check(tc["input"])
                    yield _sse({"type": "tool_done", "tool": "check_whatsapp"})

                else:
                    result = f"Unknown tool: {tool_name}"

                tool_result_content.append({
                    "type":        "tool_result",
                    "tool_use_id": tc["id"],
                    "content":     result,
                })

            messages_2 = messages + [
                {"role": "assistant", "content": first_response.content},
                {"role": "user",      "content": tool_result_content},
            ]

            # Stream Claude's response that incorporates search results
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages_2,
            ) as stream2:
                async for event in stream2:
                    if getattr(event, "type", None) == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text") and delta.text:
                            full_text += delta.text
                            yield _sse({"type": "chunk", "text": delta.text})

        expression = classify_expression(full_text)
        yield _sse({"type": "done", "expression": expression})

        # ── Store turn in memory (after done event) ────────────────────────
        if full_text.strip():
            try:
                from backend.memory_store import add_turn
                add_turn(message, full_text)
            except Exception as mem_exc:
                log.debug("Memory store skipped: %s", mem_exc)

    except anthropic.AuthenticationError:
        yield _sse({"type": "error_replace", "text": (
            "Your Anthropic API key looks invalid. "
            "Please update it in ⚙ Settings → API Keys."
        )})
        yield _sse({"type": "done", "expression": "confused"})

    except anthropic.APIConnectionError:
        yield _sse({"type": "error_replace", "text": (
            "Can't reach the Anthropic API right now. "
            "Please check your internet connection and try again."
        )})
        yield _sse({"type": "done", "expression": "confused"})

    except anthropic.RateLimitError:
        yield _sse({"type": "error_replace", "text": (
            "Rate limit hit — please wait a moment and try again."
        )})
        yield _sse({"type": "done", "expression": "confused"})

    except Exception as exc:
        log.error("Unexpected Claude error: %s", exc, exc_info=True)
        yield _sse({"type": "error_replace", "text": f"Something went wrong: {exc}"})
        yield _sse({"type": "done", "expression": "confused"})
