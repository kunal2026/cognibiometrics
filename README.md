# Cognitive-Biometric Web Dashboard Prototype

This project is a **web-based, interactive, visually rich dashboard** for your cognitive-biometric system.

It is perfect for case **B-1**: run the server somewhere (laptop, VPS, cloud) and open the dashboard from **mobile or any browser** via URL.

## 1. Structure

- `backend/`
  - `app.py` – FastAPI app (API + serving frontend)
  - `agent.py` – CognitiveAgent + keystroke/app monitoring
  - `config.py` – parameters
  - `requirements.txt` – Python dependencies
- `frontend/`
  - `index.html` – single-page dashboard (Tailwind + Chart.js)

## 2. Running Locally (for testing)

### 2.1. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # on Windows
pip install -r requirements.txt
```

### 2.2. Start server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Then on the **same machine** open:

- http://127.0.0.1:8000/

To open from **your phone on same Wi‑Fi**, replace 127.0.0.1 with your laptop's IP, e.g.:

- http://192.168.1.5:8000/

## 3. Making it Public (Cloud / ngrok style)

### Option A – Use ngrok (fast for demo)

1. Install ngrok from https://ngrok.com/
2. Run the FastAPI server as above (uvicorn on port 8000).
3. In another terminal:

```bash
ngrok http 8000
```

4. ngrok will give you a URL like:

- https://abcd-1234.ngrok-free.app/

Open that URL on **your mobile** – you'll see the dashboard.

### Option B – Deploy to cloud (Render / Railway / EC2 etc.)

- Copy the `backend/` folder to your cloud environment.
- Install Python 3.10+, `pip install -r requirements.txt`.
- Configure the service to run:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

- Expose port 8000 (or platform default) and map it to a public URL.
- Ensure `../frontend/index.html` and folder are present relative to backend.

Then you can open the public URL from anywhere, including your **phone**, with full interactivity.

