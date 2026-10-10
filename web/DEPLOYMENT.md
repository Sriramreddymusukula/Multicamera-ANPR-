# Deploy Meridian on an Ubuntu server

Meridian is a single-origin application: FastAPI serves the Vite production build and `/api`. It also runs YOLOv8, OpenCV, and Tesseract OCR. A static-only host cannot run detection. These steps assume an Ubuntu VM, a domain name, and a non-root deployment user.

## 1. Prepare the server

Install Python with `venv`, Node.js compatible with the frontend's Vite version (Node `^20.19.0` or `>=22.12.0`), Nginx, and OCR/system libraries:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr libgl1 libglib2.0-0 nginx
node --version
```

Install Node.js from its official distribution instructions if the installed version does not meet the version above. For CPU-only or CUDA-specific PyTorch packages, use the [official PyTorch selector](https://pytorch.org/get-started/locally/) before installing the remaining requirements.

## 2. Copy and build the application

As the deployment user, place the repository at `/opt/meridian` (replace this path in the service example if needed):

```bash
cd /opt/meridian
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt -r web/backend/requirements-web.txt
cd web/frontend
npm ci
npm run build
cd ../..
venv/bin/python -m pytest -q
```

Confirm `models/best.pt` is present, `tesseract --version` works, and the deployment user can write `vehicle_database.csv`, `output/`, and `web/backend/` (SQLite and temporary uploads live there).

## 3. Set the session secret

Create `/etc/meridian.env` with a long random value and restrict it to the account running the service:

```text
ANPR_WEB_SECRET=replace-with-a-random-secret
```

Keep this value stable across restarts. If it changes, existing sessions become invalid. Do not commit the file. Back up `vehicle_database.csv`, `output/`, and `web/backend/web_users.db` together; these hold observations, evidence, and accounts.

## 4. Run FastAPI as a service

Create `/etc/systemd/system/meridian.service`, replacing `meridian` with your deployment username if different:

```ini
[Unit]
Description=Meridian City Intelligence
After=network.target

[Service]
User=meridian
WorkingDirectory=/opt/meridian
EnvironmentFile=/etc/meridian.env
ExecStart=/opt/meridian/venv/bin/python -m uvicorn app.main:app --app-dir /opt/meridian/web/backend --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meridian
sudo systemctl status meridian
curl http://127.0.0.1:8000/api/health
```

Use one application process initially. The current video job store is in process memory, so multiple workers would not share job status. Benchmark CPU and memory use with your actual model and videos before increasing traffic.

## 5. Put Nginx and HTTPS in front

Create `/etc/nginx/sites-available/meridian` with this server block, replacing the domain:

```nginx
server {
    listen 80;
    server_name meridian.example.com;
    client_max_body_size 310M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

Enable the site, test and reload Nginx, then [enable HTTPS with Certbot](https://certbot.eff.org/instructions?os=snap&ws=nginx) or your hosting provider's certificate manager. Keep Uvicorn bound to `127.0.0.1`.

```bash
sudo ln -s /etc/nginx/sites-available/meridian /etc/nginx/sites-enabled/meridian
sudo nginx -t
sudo systemctl reload nginx
```

The frontend uses relative `/api` URLs, so the website and API must be served from the same public origin. Check `/`, `/overview`, `/console` (redirects to login anonymously), `/api/health`, and an actual operator upload after deployment.

**Before an internet-facing deployment with real vehicle data:** the current `.cop@` rule validates email format, not operator identity. Restrict account creation to trusted staff or add email verification/approval, and define retention and access policies for stored registration data and evidence.
