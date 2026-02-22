import httpx


class CometClient:
    def __init__(self, token: str, model: str = "gpt-5.1", base_url: str = "https://api.cometapi.com"):
        self.token = token
        self.model = model
        self.url = f"{base_url.rstrip('/')}/v1/chat/completions"

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
            r = await client.post(self.url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
