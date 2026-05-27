import logging

from openai import OpenAI

from launchmind.utils import retry

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


@retry(max_attempts=3, delay=1.0)
def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    logger.debug("LLM response (%d chars): %.100s...", len(content), content)
    return content
