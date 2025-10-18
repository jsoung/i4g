# bge_embed_server.py
from fastapi import FastAPI, Request
from sentence_transformers import SentenceTransformer
import uvicorn

app = FastAPI()
model = SentenceTransformer("BAAI/bge-small-en")

@app.post("/embed")
async def embed(request: Request):
    data = await request.json()
    texts = data.get("input", [])
    embeddings = model.encode(texts, convert_to_numpy=True).tolist()
    return {"data": [{"embedding": emb} for emb in embeddings]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
