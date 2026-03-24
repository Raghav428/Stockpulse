from fastapi import FastAPI, Path

app = FastAPI()

@app.get("/health")
async def health():
    return {"status" : "ok"}

@app.get("/stock/{symbol}")
async def stock(symbol : str = Path(min_length=1, max_length=5, pattern= r"^[A-Z]+$")):
    return {
        "symbol" : symbol,
        "price" : 3*int(len(symbol)) + 2,
        "date_listed" : "23/01/2003"

    }