# CodeAutopsy Developer Setup: Local Ollama AI

CodeAutopsy uses **Ollama** combined with the `qwen2.5-coder:3b` model to perform extremely fast, local static analysis and fix generation without relying on expensive cloud APIs. 

To improve reliability and development speed, **Ollama is decoupled from the main Docker stack**. This ensures that starting or stopping the backend containers does not cause the heavy AI model to reload.

This guide explains how to install, configure, and connect Ollama to the CodeAutopsy backend.

---

## 1. Install Ollama

First, install the Ollama daemon on your host machine.

- **macOS / Windows**: Download the official installer from [ollama.com](https://ollama.com/download).
- **Linux**: Run the official installation script:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

---

## 2. Pull the AI Model

Start the Ollama daemon if it isn't running already, then pull the required CodeAutopsy model:

```bash
ollama pull qwen2.5-coder:3b
```

*Note: This model is around ~1.9GB. Once pulled, it will be stored securely on your host machine.*

---

## 3. Configure Network Binding

By default, Ollama only listens on `127.0.0.1` (localhost). For the Dockerized CodeAutopsy backend to communicate with the host machine's Ollama instance, Ollama *must* be bound to all network interfaces (`0.0.0.0`).

### On macOS / Windows:
If you are using the desktop app, you need to set the `OLLAMA_HOST` environment variable before launching the app, or run it through the terminal:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### On Linux (systemd):
1. Overwrite the systemd service configuration:
   ```bash
   sudo systemctl edit ollama.service
   ```
2. Add the following under the `[Service]` section to expose the port:
   ```ini
   [Service]
   Environment="OLLAMA_HOST=0.0.0.0"
   ```
3. Reload and restart the daemon:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart ollama
   ```

---

## 4. Connect the Backend

Update the CodeAutopsy backend configuration so it knows where to find your external Ollama server. 

In `backend/.env`, ensure the `OLLAMA_BASE_URL` is set correctly:

- **If running the backend via Docker Compose**: 
  Docker maps `host.docker.internal` to your host machine's IP.
  ```env
  # Default for backend/.env
  OLLAMA_BASE_URL=http://host.docker.internal:11434
  ```
  *(Note for Linux users: If `host.docker.internal` fails to resolve, use your machine's local IP address, e.g., `http://192.168.1.50:11434`)*

- **If running the backend natively (e.g. `uvicorn main:app`)**:
  ```env
  OLLAMA_BASE_URL=http://localhost:11434
  ```

---

## 5. Verify Setup

Check that Ollama is accessible. Open a terminal and run:

```bash
# Verify it works locally
curl http://localhost:11434/api/tags

# If you want to verify it works across your network / Docker bridge:
# Replace localhost with your IP or host.docker.internal
curl http://host.docker.internal:11434/api/tags
```

You should see a JSON response confirming that `qwen2.5-coder:3b` is available in your model list.

---

## Troubleshooting

### Connection Refused (`httpx.ConnectError`)
- **Reason:** The backend cannot reach Ollama at the specified URL.
- **Fix:** Ensure `ollama serve` is actively running. Verify that you bound the server to `0.0.0.0` securely (see Step 3), as it defaults to `127.0.0.1` and blocks external Docker traffic.

### Model Not Found / Unreachable
- **Reason:** Ollama is running, but the requested model is missing.
- **Fix:** Run `ollama list` to view installed models. If `qwen2.5-coder:3b` is missing, run `ollama pull qwen2.5-coder:3b`.

### Firewall Restrictions
- If you are on Windows or Linux, ensure your firewall (Windows Defender, UFW, or firewalld) allows incoming TCP traffic on port `11434`.
  - Ubuntu/UFW: `sudo ufw allow 11434/tcp`
