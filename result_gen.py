from openai import OpenAI
from config import key


def api_get_result(text):
    client = OpenAI(
      base_url="https://openrouter.ai/api/v1",
      api_key=key,
    )

    completion = client.chat.completions.create(
      model="openai/gpt-oss-20b:free",
      messages=[
        {
          "role": "user",
          "content": f"{text}"
        }
      ]
    )

    return completion.choices[0].message.content


def split_message(text: str, limit: int = 4000):
    parts = []
    while len(text) > limit:
        split_pos = text.rfind("\n", 0, limit)
        if split_pos == -1:
            split_pos = limit
        parts.append(text[:split_pos])
        text = text[split_pos:]
    parts.append(text)
    return parts