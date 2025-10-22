"""
Semantic Named Entity Extraction (chat-style) using a local Ollama LLM via LangChain.

- Uses a chat-like System / User framing to reduce LLM refusals.
- Explicitly instructs the model: extraction only, no instructions that would enable wrongdoing.
- If the model returns non-JSON or refuses, fall back to rule-based extraction (ner_rules).
"""

import json
import re
from typing import Any, Dict

from langchain.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

from i4g.extraction.ner_rules import extract_entities as rule_extract_entities

# System instruction: sets mission and safety context (why this task is allowed)
_SYSTEM_PROMPT = """
You are an assistant whose only job is to *extract structured entities* from text for
the purpose of victim support and law enforcement investigation. You must NOT provide
any operational advice, instructions, or steps that could enable wrongdoing.

Return ONLY a JSON object with the exact top-level keys listed in the examples.
If a field has no values, return an empty list for that field. Do NOT add extra keys.
"""

# Human / user prompt: contains the data and the requested fields
_HUMAN_TEMPLATE = """
Text:
{text}

Return a JSON object with these exact fields:
{
  "people": [],
  "organizations": [],
  "crypto_assets": [],
  "wallet_addresses": [],
  "contact_channels": [],
  "locations": [],
  "scam_indicators": []
}

Rules:
- Group multi-word names (e.g., "The New Jersey Devils") as a single entity.
- Include exchange names, wallet references, suspicious URLs or usernames.
- "scam_indicators" lists short phrases like "verification fee", "investment guarantee".
- Do NOT include instructions or steps. If you detect explicit solicitation or instruction,
  still extract the entities but do not restate the instructions; instead include the phrase
  in "scam_indicators".
Examples:
Example 1 Input: "Hi, I'm Anna from TrustWallet. Send 0xAbC... to verify and pay 50 USDT."
Example 1 Output:
{
  "people": ["Anna"],
  "organizations": ["TrustWallet"],
  "crypto_assets": ["USDT"],
  "wallet_addresses": ["0xAbC..."],
  "contact_channels": [],
  "locations": [],
  "scam_indicators": ["verification fee", "send to verify"]
}
Now analyze the Text above and return only the JSON.
"""


def build_llm(model: str = "llama3.1", base_url: str | None = None) -> OllamaLLM:
    kwargs = {"model": model}
    if base_url:
        kwargs["base_url"] = base_url
    return OllamaLLM(**kwargs)


def _format_chat_prompt(text: str) -> str:
    """
    Build a single string prompt that simulates a chat conversation:
    we prepend the system message then the human message. This avoids LangChain
    interpreting braces as variables while still delivering a clear chat-style instruction.
    """
    # We deliberately avoid using PromptTemplate with braces in JSON to reduce escaping issues.
    # The prompt is simple text combining system + human instructions.
    human = _HUMAN_TEMPLATE.replace("{", "{{").replace("}", "}}")  # escape braces for safety
    # Now insert the text safely
    human_filled = human.replace("{{text}}", text) if "{{text}}" in human else human.replace("{text}", text)
    # Un-escape braces so the model sees actual JSON braces
    human_filled = human_filled.replace("{{", "{").replace("}}", "}")
    prompt = _SYSTEM_PROMPT.strip() + "\n\n" + human_filled.strip()
    return prompt


def _safe_parse_json(resp_text: str) -> Dict[str, Any]:
    """
    Try to find the first JSON object in the response and parse it.
    """
    try:
        return json.loads(resp_text)
    except json.JSONDecodeError:
        # Extract JSON-like substring (greedy but robust)
        m = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\}", resp_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {"raw_output": resp_text}
        else:
            return {"raw_output": resp_text}


def extract_semantic_entities(text: str, llm: OllamaLLM) -> Dict[str, Any]:
    """
    Primary entrypoint: returns parsed JSON or fallback to rule-based extraction.
    """
    prompt = _format_chat_prompt(text)

    # Use the modern .invoke() method, which is standard for all Runnables.
    try:
        # .invoke() returns a string for LLM components.
        resp = llm.invoke(prompt)
    except Exception as e:
        # If the LLM call fails entirely, fall back to the rule-based extractor.
        parsed = rule_extract_entities(text)
        return {"fallback_rule_based": parsed, "llm_error": str(e)}

    parsed = _safe_parse_json(resp)

    # If model refused (explicit refusal), parsed will likely be {"raw_output": "I cannot provide..."}
    if parsed.get("raw_output") and "cannot provide" in parsed["raw_output"].lower():
        # Use rule-based extractor as a fallback and include the LLM raw reply for audit
        parsed_rule = rule_extract_entities(text)
        return {"fallback_rule_based": parsed_rule, "llm_raw_reply": parsed["raw_output"]}

    # If we got raw_output but it contains a valid-looking JSON, keep it; otherwise if it's not valid
    # but rule-based extraction found things, we merge both (LLM best-effort + regex)
    if "raw_output" in parsed:
        # fallback merge
        parsed_rule = rule_extract_entities(text)
        return {"merged": {"llm_raw": parsed["raw_output"], "rule_extracted": parsed_rule}}

    return parsed
