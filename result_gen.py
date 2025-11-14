from openai import OpenAI


def api_get_result(text):
    client = OpenAI(
      base_url="https://openrouter.ai/api/v1",
      api_key="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",
    )

    completion = client.chat.completions.create(
      # extra_headers={
      #   "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
      #   "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
      # },
      model="google/gemini-2.0-flash-exp:free",
      messages=[
        {
          "role": "user",
          "content": f"{text}"
        }
      ]
    )

    return completion.choices[0].message.content

