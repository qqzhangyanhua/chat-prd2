from fastapi import FastAPI

app = FastAPI(title="AI Co-founder API")


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
