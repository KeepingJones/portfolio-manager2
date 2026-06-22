import json
import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from database import db
from routers.summary import get_summary

router = APIRouter(prefix="/api/ai", tags=["ai"])

def get_ollama_settings():
    with db() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM portfolio_settings").fetchall()}
    return {
        "url": rows.get("ollama_url", "http://localhost:11434"),
        "model": rows.get("ollama_model", "llama3")
    }

@router.get("/models")
async def get_ollama_models():
    settings = get_ollama_settings()
    url = settings["url"].rstrip('/') + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"status": "ok", "models": models}
            return {"status": "error", "message": f"Ollama returned {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def build_portfolio_prompt() -> str:
    # Gather data
    summary = get_summary()
    with db() as conn:
        positions_raw = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
    
    for p in positions_raw:
        p['current_value'] = (p.get('units') or 0) * (p.get('last_price') or p.get('book_cost_per_unit') or 0)
        
    positions = sorted(positions_raw, key=lambda x: x['current_value'], reverse=True)
    # Format a text summary
    prompt = f"""You are an expert financial advisor and portfolio analyst.
Analyze the following portfolio and provide a professional, structured review.

## Portfolio Summary
- Total Value: £{summary['total_current_value']}
- Book Cost: £{summary['total_book_cost']}
- Capital Growth: £{summary['capital_growth']} ({summary['capital_growth_pct']}%)
- Projected Annual Income: £{summary['annual_dividend_income_est']} (Yield: {(summary['annual_dividend_income_est']/max(1, summary['total_current_value'])*100):.2f}%)
- Number of Positions: {summary['positions_count']}

## Asset Allocation
"""
    for atype, data in summary['by_asset_type'].items():
        prompt += f"- {atype.capitalize()}: £{data['value']} ({data['count']} positions)\n"

    prompt += "\n## Top Holdings\n"
    for p in positions[:10]:
        val = p.get('units', 0) * (p.get('last_price') or p.get('book_cost_per_unit', 0))
        prompt += f"- {p['name']} ({p.get('ticker') or p.get('isin')}): £{val:.2f} (Asset Type: {p.get('asset_type')}, Category: {p.get('category')})\n"
        
    prompt += """
Please structure your response with markdown headers. Include the following sections:
1. **Executive Summary**: A brief overall impression.
2. **Asset Allocation & Diversification**: Critique the balance between asset classes and categories.
3. **Income & Yield Analysis**: Comment on the dividend sustainability and yield.
4. **Risk Factors & Recommendations**: Highlight any concentration risks or areas for improvement.

Keep it concise, professional, and actionable. Do not give direct financial advice, just analytical observations.
"""
    return prompt

@router.get("/analyze")
async def analyze_portfolio():
    settings = get_ollama_settings()
    prompt = build_portfolio_prompt()
    
    ollama_url = settings["url"].rstrip('/') + "/api/generate"
    
    payload = {
        "model": settings["model"],
        "prompt": prompt,
        "stream": True
    }
    
    async def stream_ollama():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", ollama_url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"Error: Ollama API returned status {response.status_code}"
                        return
                        
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            yield f"\n\n**Error connecting to Ollama**: {str(e)}\nPlease make sure Ollama is running at {settings['url']} and the model '{settings['model']}' is pulled."

    return StreamingResponse(stream_ollama(), media_type="text/plain")
