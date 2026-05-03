# DCF Engine — Ashish Ambashankar

Discounted Cash Flow valuation tool with live Yahoo Finance data.
Portable — runs on any server that supports Python.

---

## Files

| File              | Purpose                                      |
|-------------------|----------------------------------------------|
| `api.py`          | FastAPI server — serves UI and API routes    |
| `model.py`        | DCF engine — fetch, calculate, scenarios     |
| `dcf_engine.html` | Full frontend (served by api.py at `/`)      |
| `requirements.txt`| Python dependencies                          |
| `Procfile`        | For Render / Railway / Heroku                |
| `Dockerfile`      | For VPS / Fly.io / DigitalOcean / any Docker |

---

## Run locally (any machine with Python)

```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Open: http://localhost:8000

---

## Deploy — choose your platform

### Render (free tier, recommended)
1. Push this folder to GitHub
2. render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
5. Deploy

### Railway
1. Push to GitHub
2. railway.app → New Project → Deploy from GitHub
3. Railway auto-detects the Procfile — no config needed
4. Deploy

### Fly.io
```bash
brew install flyctl
flyctl auth login
flyctl launch        # auto-detects Dockerfile
flyctl deploy
```

### DigitalOcean / any VPS
```bash
git clone <your-repo>
cd dcf_engine
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```
Use nginx as a reverse proxy if you want it on port 80/443.

### Docker (any Docker-capable server)
```bash
docker build -t dcf-engine .
docker run -p 8000:8000 dcf-engine
```

### Hugging Face Spaces (free, easy)
1. Create a new Space → SDK: Docker
2. Push all files as-is
3. Change `EXPOSE` and port in Dockerfile to `7860` (HF requirement)
4. Live at `https://huggingface.co/spaces/your-username/dcf-engine`

---

## Ticker formats
- Indian NSE: `RELIANCE.NS` · `TCS.NS` · `INFY.NS` · `HDFCBANK.NS`
- US: `AAPL` · `MSFT` · `GOOGL` · `TSLA`
- Search by company name in the search bar

---

Data via Yahoo Finance · Not financial advice
LinkedIn: https://www.linkedin.com/in/ashish-ambashankar
TVM Calculator: https://ashish-tvm-calculator.netlify.app/
