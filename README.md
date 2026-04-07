<div align="center">
  
# 🧬 CodeAutopsy
**A Time Machine for Debugging & Code Analysis**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/react-19-blue.svg?logo=react&logoColor=white)](https://react.dev/)
[![FastAPI](https://img.   shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Languages Supported](https://img.shields.io/badge/Languages-369-purple.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Don't just find bugs — discover **when** they were introduced, **who** wrote them, and **how** they evolved.*

[Explore Features](#✨-features) • [Installation](#🚀-quick-start) • [API Reference](#🌐-api-reference) • [Roadmap](#🛣-roadmap)

</div>

---

## 🔬 What is CodeAutopsy?

CodeAutopsy is an advanced, web-based code analysis platform that bridges the gap between **static security scanning**, **Git forensics**, and **AI-powered intelligence**. 

While traditional tools might only tell you *"Line 45 has a SQL injection vulnerability,"* CodeAutopsy provides the full story:
- 📈 **The Timeline:** A visual history of how the problematic code evolved across multiple commits.
- 👤 **The Author:** Precise identification of who introduced the vulnerability and when.
- 🤖 **The Fix:** AI-generated remediation strategies backed by confidence scoring.
- 🌐 **The Scope:** Automatic detection and support for over 360 programming languages.

---

## ✨ Features

We pack a suite of powerful tools into a single, cohesive dashboard to make code analysis seamless and insightful.

### 🛡️ Comprehensive Static Analysis & Security Scanning
- **Dual-Engine Scanning:** Built-in regex-based scanner with over 16 tailored security rules, plus automatic integration with **Semgrep** for scanning against 1000+ advanced rules if installed.
- **Code Health Scoring:** Instantly evaluate your project with a comprehensive Code Health Score (0–100) based on vulnerability density and complexity.

### 🧬 Git Forensics & Code Archaeology
- **Timeline Visualization:** Trace the exact origin of a bug in your git history.
- **Git Blame Integration:** Understand the context behind code changes by seeing who modified what, and why.
- **File Evolution Tracking:** Watch how specific files and functions have morphed over time.

### 🤖 AI-Powered Insights (Powered by Groq)
- **Automated Fix Suggestions:** Highlight a vulnerability and get instant, AI-generated code fixes.
- **Confidence Scoring:** AI suggestions come with a confidence score and detailed explanation so you can trust the changes.

### 📝 Interactive In-Browser Experience
- **Monaco Code Editor:** A full-fledged, VS Code-like editor built right into the browser for seamless code viewing and experimentation.
- **Real-Time Progress:** Watch the analysis happen live via Server-Sent Events (SSE) streaming.
- **Modern UI/UX:** A beautiful, responsive interface with Dark/Light mode toggles, built with Tailwind CSS and Framer Motion for smooth animations.

### 📊 Deep Project Analytics
- **Massive Language Support:** Automatically detects 369 programming languages across 904 file extensions.
- **Rich Reporting:** Export your findings as raw JSON data or as beautifully styled PDF reports for stakeholder meetings.

---

## 🛠 Tech Stack

CodeAutopsy is built with modern, high-performance technologies:

| Layer | Technologies |
|-------|--------------|
| **Frontend** | React 19, Vite 8, Tailwind CSS v4, Framer Motion, Zustand (State Management), Recharts, Monaco Editor, Lucide Icons |
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy, GitPython |
| **Analysis Engine**| Built-in Regex Scanner, Semgrep (optional) |
| **Artificial Intelligence** | Groq API |
| **Database** | SQLite (Zero-config, ready to go) |

---

## 🚀 Quick Start

Get CodeAutopsy up and running on your local machine in minutes.

### Prerequisites
Make sure you have the following installed:
- **Python 3.10+**
- **Node.js 18+**
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/Sivanandhpp/CodeAutopsy.git
cd CodeAutopsy
```

### 2. Backend Setup
Navigate to the backend directory, set up your virtual environment, and install dependencies.

```bash
cd backend
python -m venv venv

# Activate standard virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

**Environment Variables**
Create a `.env` file from the example:
```bash
cp .env.example .env
```
Populate `.env` with your keys:
```env
# Required for AI features
GROQ_API_KEY=gsk_your_key_here

# Optional: Increases GitHub API rate limit for large repos
GITHUB_TOKEN=ghp_your_token_here

# Database config (SQLite works automatically)
DATABASE_URL=sqlite:///./data/codeautopsy.db

# CORS configuration
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Start the API Server:**
```bash
python -m uvicorn app.main:app --reload --port 8000
```
*You should see a message confirming the API is running and connected to the database.*

### 3. Frontend Setup
Open a new terminal window, navigate to the frontend directory, and start the Vite dev server.

```bash
cd frontend
npm install
npm run dev
```
The application will be live at: **`http://localhost:5173`**

### 4. Try It Out!
1. Open your browser and navigate to `http://localhost:5173`.
2. Enter any public GitHub URL (e.g., `https://github.com/pallets/flask`).
3. Click **Analyze** and watch the SSE stream build your results in real-time.
4. Explore the Dashboard, view the Health Score, and inspect code in the Monaco Editor.

---

## 🔌 Optional: Enhanced Analysis with Semgrep
Want deeper security coverage? Install Semgrep globally in your environment. CodeAutopsy will automatically detect it and upgrade its scanning capabilities.
```bash
pip install semgrep
```

---

## 🌐 API Reference

CodeAutopsy provides a robust REST API for custom integrations:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check API and Database status |
| `POST` | `/api/analyze/github` | Trigger a new repository analysis |
| `GET` | `/api/analyze/stream/{id}` | Connect to SSE for real-time analysis progress |
| `GET` | `/api/results/{id}` | Fetch completed analysis results and scores |
| `GET` | `/api/files/{id}?path=...` | Read file contents from an analyzed repository |
| `GET` | `/api/archaeology/trace/{id}`| Trace code history and git blame |
| `POST` | `/api/ai/analyze` | Request AI-generated fixes and explanations |
| `GET` | `/api/report/{id}/json` | Export full results as JSON |
| `GET` | `/api/report/{id}/pdf` | Generate and download a PDF report |

---

## 🛣 Roadmap

- [x] **v0.1:** Core foundation, landing page, responsive dark/light mode UI.
- [x] **v0.2:** GitHub integration, built-in static analysis rules, Results Dashboard.
- [x] **v0.3:** Code Archaeology Engine (Git blame, timeline evolution tracking).
- [x] **v0.4:** In-browser code editing and exploration with Monaco.
- [x] **v0.5:** AI Integration (Groq) for automated insights and fix suggestions.
- [x] **v0.6:** PDF/JSON Exporting and Semgrep auto-detection integration.
- [ ] **Upcoming:** Custom scanning rules, CI/CD pipeline integration, Docker support.

---

## 🤝 Contributing

We welcome contributions! To get started:
1. Fork the project.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License & Credits

Distributed under the MIT License. See `LICENSE` for more information.

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/Sivanandhpp">Sivanandh P P</a></p>
</div>
