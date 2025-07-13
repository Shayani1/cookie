# Quotex Cookie Refresher

Headless FastAPI service that logs into https://market-qx.pro/ and refreshes session cookies every 30 minutes.

## Environment variables
- `QX_EMAIL` — Quotex login email
- `QX_PASSWORD` — Quotex password
- `REFRESH_MINS` — optional refresh interval (default 30)

## Local run

```bash
pip install -r requirements.txt
playwright install
export QX_EMAIL="you@example.com"
export QX_PASSWORD="password"
python main.py
```

## Deploy on Railway

1. Create new project → Deploy from Repo/Zip  
2. Add required environment variables in *Variables* tab  
3. Railway will build and start automatically (Procfile included)  

Access latest session at:
```
GET https://<your-app>.up.railway.app/get-cookies
```
