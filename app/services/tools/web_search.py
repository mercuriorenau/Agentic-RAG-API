from typing import Any

import httpx


async def web_search(query: str, *, api_key: str, max_results: int = 5) -> dict[str, Any]:
    if not api_key:
        return {"unavailable": True, "results": []}

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return {"error": str(exc), "results": []}

    results = []
    for item in data.get("results") or []:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": item.get("content") or "",
                "score": item.get("score"),
            }
        )
    return {"results": results}
