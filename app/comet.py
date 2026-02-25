import httpx


class CometClient:
    def __init__(self, token: str, model: str = "gpt-5.1", base_url: str = "https://api.cometapi.com"):
        self.token = token
        self.model = model
        root = base_url.rstrip("/")
        self.chat_url = f"{root}/v1/chat/completions"
        self.responses_url = f"{root}/v1/responses"

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(self.chat_url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

    async def web_search(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": prompt,
            "tools": [{"type": "web_search_preview"}],
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                r = await client.post(self.responses_url, headers=headers, json=payload)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in {400, 422}:
                    raise
                fallback_payload = {
                    "model": self.model,
                    "input": prompt,
                    "tools": [{"type": "web_search"}],
                }
                r = await client.post(self.responses_url, headers=headers, json=fallback_payload)
                r.raise_for_status()

            data = r.json()

        # CometAPI may pass through different provider response formats.
        output_text = data.get("output_text")
        if output_text:
            return output_text

        if "choices" in data:
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content")
                if isinstance(content, str):
                    return content

        output = data.get("output") or []
        chunks: list[str] = []
        for item in output:
            for part in item.get("content", []):
                if part.get("type") in {"output_text", "text"}:
                    txt = part.get("text", "")
                    if txt:
                        chunks.append(txt)
        if chunks:
            return "\n".join(chunks)

        raise RuntimeError("Comet responses API returned no text output")
