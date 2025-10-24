from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/status")
def status():
    return {"ok": True, "service": "baseline-app"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
