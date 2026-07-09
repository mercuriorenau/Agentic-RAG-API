from openai import AsyncOpenAI

from app.core.config import Settings, get_settings


class EmbeddingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0]
