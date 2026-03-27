"""SerpAPI MCP Server — exposes web_search tool via Streamable HTTP."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("serpapi-search", stateless_http=True)


@mcp.tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using SerpAPI. Returns titles, snippets, and URLs."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://serpapi.com/search.json",
            params={
                "q": query,
                "api_key": os.environ["SERPAPI_API_KEY"],
                "num": min(num_results, 10),
            },
            timeout=15,
        )
    results = resp.json().get("organic_results", [])[:num_results]
    if not results:
        return f"No results found for: {query}"
    return "\n\n".join(
        f"**{r.get('title', '')}**\n{r.get('snippet', '')}\nURL: {r.get('link', '')}"
        for r in results
    )


if __name__ == "__main__":
    # Host/port configured via MCP_HOST and MCP_PORT env vars (defaults: 0.0.0.0:8000)
    # Or via uvicorn directly for custom port
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
