# ⚖️ HuquqPlus — Open Legal Intelligence & Consultation Platform

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Aiogram 3](https://img.shields.io/badge/Aiogram-3.10-2CA5E0.svg?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-5.0-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![SQLModel](https://img.shields.io/badge/SQLModel-Alembic-E32943.svg)](https://sqlmodel.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**HuquqPlus** is an open-source, high-throughput legal technology infrastructure designed to bridge the gap between citizens, legal professionals, and volunteer jurists in Uzbekistan. Built with modern asynchronous Python, the platform provides automated citizen inquiry intake, lawyer consultation dispatching, volunteer management analytics, and automated multi-channel reporting.

---

## 🏛️ Key Features

- **⚡ Asynchronous API Engine**: Powered by **FastAPI** with dependency injection, strict Pydantic v2 schemas, and high-concurrency request routing.
- **🤖 Omnichannel Telegram Bot**: Built on **Aiogram 3.x** with custom middleware, session management, multi-lingual keyboards, and rate limiting.
- **🔄 Distributed Task Queues**: **Celery** with **Redis** broker for background broadcast dispatch, daily reminders, appointment notifications, and analytics aggregation.
- **👥 Professional & Volunteer Workflows**:
  - Citizen inquiry triage and priority categorization.
  - Appointment scheduling with automated SMS/Telegram reminders.
  - Volunteer lawyer leaderboard and impact analytics.
- **📊 Reporting & Export Engine**: Automated generation of daily, weekly, and monthly performance reports in Excel (`openpyxl` / `xlsxwriter`) and PDF formats.
- **🐳 Enterprise Production Ready**: Full Docker & Docker Compose orchestration with health checks, Alembic database migrations, and Gunicorn/Uvicorn process workers.

---

## 🏗️ Architecture Overview

```
                      +-----------------------------+
                      |   Citizens / Telegram Users |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Telegram Bot (Aiogram 3.x) |
                      +--------------+--------------+
                                     |
                                     v
+------------------+         +-------+-------+         +-------------------+
|  Public API &    | <-----> |   FastAPI     | <-----> | Celery Background |
|  Admin Dashboard |         |  Core Engine  |         | Worker & Beat     |
+------------------+         +-------+-------+         +---------+---------+
                                     |                           |
                    +----------------+----------------+          |
                    |                                 |          v
                    v                                 v    +---------------+
          +-------------------+             +------------+ | Redis Message |
          | MySQL (SQLModel)  |             | Alembic    | | Broker/Cache  |
          | Persistent Store  |             | Migrations | +---------------+
          +-------------------+             +------------+
```

---

## 📂 Project Structure

```
├── docker/                      # Production Docker scripts & entrypoints
├── src/
│   ├── app/                     # Business logic, analytics & formatters
│   │   ├── volunteer_analytics.py # Performance tracking for jurists
│   │   ├── calendar_utils.py    # Calendar & appointment computations
│   │   ├── generate_report.py   # Automated Excel & PDF generators
│   │   └── keyboards.py         # Dynamic Telegram interactive menus
│   ├── config/                  # App configuration & environment settings
│   ├── database/                # MySQL connection, Redis pool & Alembic setup
│   ├── models/                  # SQLModel database models (Users, Inquiries, Lawyers)
│   ├── routes/                  # FastAPI endpoints & dependency injections
│   ├── tasks/                   # Celery asynchronous tasks (broadcasts, reminders)
│   ├── main.py                  # API server startup & lifespan handlers
│   └── worker.py                # Celery worker process entrypoint
├── docker-compose.yaml          # Local development stack
├── docker-compose.prod.yaml     # Production container orchestration
├── pyproject.toml               # Poetry dependency declarations
└── alembic.ini                  # Database migration configuration
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.11+**
- **Docker & Docker Compose** (optional, recommended for production)
- **Redis & MySQL / MariaDB**

### 2. Clone & Environment Setup
```bash
git clone https://github.com/mansurxongemini/Huquqplus.uz.git
cd Huquqplus.uz

# Copy example environment configuration
cp .env.example .env
```

Edit `.env` to configure your database credentials, Telegram Bot Token, and Redis URL.

### 3. Running with Docker Compose (Recommended)
```bash
docker compose up -d --build
```
This spins up:
- FastAPI Web API (`http://localhost:8000`)
- Interactive API Docs (`http://localhost:8000/docs`)
- Celery Task Worker & Beat Scheduler
- Redis Cache & Broker

### 4. Running Locally with Poetry
```bash
# Install dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Launch FastAPI development server
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Launch Celery worker (in separate terminal)
poetry run celery -A src.worker.celery_app worker -l info
```

---

## 📑 API Documentation
Once running, explore the interactive Swagger and ReDoc documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🛡️ License
Distributed under the **MIT License**. See `LICENSE` for more information.

---

## 👨‍💻 Maintainer & Acknowledgements
- **Author**: [Mansur Rustamov](https://github.com/mansurxongemini)
- **Affiliation**: Tashkent State University of Law (TSUL)
- **Initiative**: Advancing Open Legal Tech and Pro Bono Access across Uzbekistan.
