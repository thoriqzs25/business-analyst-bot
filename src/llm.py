from openai import AsyncOpenAI

from src.config import settings

client = AsyncOpenAI(
    api_key=settings.opencode_go_api_key or "no-key",
    base_url=settings.opencode_go_base_url,
)


async def chat(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int = 8192,
) -> tuple[str, int, int]:
    response = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content or ""
    prompt_tokens = response.usage.prompt_tokens if response.usage else 0
    completion_tokens = response.usage.completion_tokens if response.usage else 0
    return text, prompt_tokens, completion_tokens


async def chat_with_messages(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 8192,
) -> tuple[str, int, int]:
    response = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content or ""
    prompt_tokens = response.usage.prompt_tokens if response.usage else 0
    completion_tokens = response.usage.completion_tokens if response.usage else 0
    return text, prompt_tokens, completion_tokens
