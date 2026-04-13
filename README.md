# Car Auctions Telegram Bot

A closed-bid car auction system built with Python, aiogram 3, PostgreSQL, and Docker.

## Features

- **Closed auctions** — participants cannot see each other's bids
- **Multi-step user registration** with admin approval and payment confirmation
- **Admin panel** via Telegram for managing users and auctions
- **Automatic auction closure** via APScheduler (every 60 seconds)
- **Winner/loser notifications** sent automatically at auction end
- **Persistent storage** via PostgreSQL with Alembic migrations
- **Docker Compose** deployment with `restart: always` for 24/7 operation

---

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your values
```

Required `.env` values:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@db:5432/car_auctions` |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `KASPI_ACCESS_FEE_LINK` | Kaspi payment link for registration fee |
| `KASPI_WINNER_LINK` | Kaspi payment link sent to auction winner |
| `ADMIN_IDS` | Comma-separated Telegram user IDs of admins |

### 2. Deploy

```bash
docker compose up -d --build
```

Migrations run automatically on startup via `alembic upgrade head`.

### 3. Enable auto-start after VPS reboot

```bash
sudo systemctl enable docker
```

---

## User Flows

### Participant Registration

```
/start → Enter name → Enter phone → Enter IIN
      → Admin reviews → Approved → Pay access fee
      → "I paid" → Admin confirms → Access granted
```

### Auction Participation

```
Auction notification → "Participate" button → Enter bid amount → Confirmed
                    → "Update Bid" button → Enter new (higher) amount → Updated
```

### Auction Lifecycle

```
Admin creates auction → Notification sent to all approved users
                     → [APScheduler checks every minute]
                     → end_time reached → Winner determined → Notifications sent
```

---

## Admin Panel Commands

| Button | Action |
|---|---|
| 📋 Create Auction | Start auction creation wizard (5 steps) |
| 🔴 Active Auctions | View active auctions with bid counts |
| ✅ Completed Auctions | View finished auctions |
| 👥 Pending Users | Review and approve/reject registrations |
| 💰 Awaiting Payment | Users waiting to pay access fee |
| ✔️ Payment Confirmations | Confirm submitted payments |
| 👤 Approved Users | List all approved participants |

---

## Project Structure

```
├── main.py                  # Entry point
├── config.py                # Settings (pydantic-settings)
├── middlewares.py           # DB session middleware
├── callbacks.py             # Callback data factories
├── models/                  # SQLAlchemy models
│   ├── user.py
│   ├── auction.py
│   └── bid.py
├── database/                # Async session factory
├── states/                  # FSM state groups
├── keyboards/               # Inline & reply keyboards
├── services/                # Business logic layer
│   ├── user_service.py
│   ├── auction_service.py
│   ├── bid_service.py
│   └── notification_service.py
├── handlers/
│   ├── common.py            # /start, /cancel
│   ├── registration.py      # Registration FSM
│   ├── admin/               # Admin handlers
│   └── participant/         # Participant handlers
├── scheduler/
│   └── tasks.py             # Auction auto-close job
├── migrations/              # Alembic migrations
│   └── versions/
│       └── 001_initial.py
├── alembic.ini
├── Dockerfile
└── docker-compose.yml
```

---

## Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Roll back last migration
alembic downgrade -1
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Bot framework | aiogram 3.7 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Scheduler | APScheduler 3.x |
| Config | pydantic-settings |
| Deployment | Docker Compose |
