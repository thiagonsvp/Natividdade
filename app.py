from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crm.db"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          company TEXT NOT NULL,
          email TEXT NOT NULL,
          phone TEXT NOT NULL,
          recurring_fee REAL NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'active',
          contract_start TEXT,
          contract_end TEXT,
          notes TEXT
        );
        CREATE TABLE IF NOT EXISTS interactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER NOT NULL,
          interaction_type TEXT NOT NULL,
          summary TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER,
          title TEXT NOT NULL,
          assignee TEXT NOT NULL,
          priority TEXT NOT NULL DEFAULT 'media',
          done INTEGER NOT NULL DEFAULT 0,
          due_date TEXT,
          FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER NOT NULL,
          reference_month TEXT NOT NULL,
          amount REAL NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          paid_at TEXT,
          FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        CREATE TABLE IF NOT EXISTS deals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          value REAL NOT NULL DEFAULT 0,
          client_name TEXT NOT NULL,
          stage TEXT NOT NULL DEFAULT 'lead',
          created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()

    if seed:
        count = cur.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if count == 0:
            cur.execute(
                "INSERT INTO clients(name,company,email,phone,recurring_fee,status,contract_start,notes) VALUES (?,?,?,?,?,?,?,?)",
                (
                    "Ana Paula",
                    "Clínica Vital",
                    "ana@clinicavital.com",
                    "(11) 99999-1111",
                    2500,
                    "active",
                    "2025-01-15",
                    "Foco em leads",
                ),
            )
            c1 = cur.lastrowid
            cur.execute(
                "INSERT INTO clients(name,company,email,phone,recurring_fee,status,contract_start) VALUES (?,?,?,?,?,?,?)",
                ("Carlos Lima", "Lima Odonto", "carlos@limaodonto.com", "(11) 98888-2222", 1800, "active", "2025-02-01"),
            )
            c2 = cur.lastrowid
            now = datetime.now().isoformat(timespec="minutes")
            cur.executemany(
                "INSERT INTO interactions(client_id,interaction_type,summary,created_at) VALUES (?,?,?,?)",
                [
                    (c1, "reuniao", "Revisão de campanha de Meta Ads", now),
                    (c1, "whatsapp", "Aprovou novo criativo", now),
                ],
            )
            cur.executemany(
                "INSERT INTO tasks(client_id,title,assignee,priority,done) VALUES (?,?,?,?,?)",
                [(c1, "Enviar relatório semanal", "João", "alta", 0), (c2, "Ajustar automação n8n", "Maria", "media", 0)],
            )
            cur.executemany(
                "INSERT INTO payments(client_id,reference_month,amount,status,paid_at) VALUES (?,?,?,?,?)",
                [(c1, "2026-02", 2500, "paid", "2026-02-05"), (c2, "2026-02", 1800, "overdue", None)],
            )
            cur.executemany(
                "INSERT INTO deals(title,value,client_name,stage,created_at) VALUES (?,?,?,?,?)",
                [
                    ("Implantação WhatsApp", 3000, "Clínica Vital", "proposal", now),
                    ("Treinamento comercial", 2200, "Lima Odonto", "lead", now),
                ],
            )
            conn.commit()
    conn.close()

def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, body="", content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        if isinstance(body, (dict, list)):
            self.wfile.write(json.dumps(body).encode())
        elif isinstance(body, str):
            self.wfile.write(body.encode())
        else:
            self.wfile.write(body)

    def _json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode() if length else "{}"
        return json.loads(raw or "{}")

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            return self._send(404, {"error": "not found"})
        return self._send(200, path.read_bytes(), content_type)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self._serve_file(TEMPLATES_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/health":
            return self._send(200, {"status": "ok"})
        if path.startswith("/static/"):
            relative_path = path.replace("/static/", "")
            file_path = (STATIC_DIR / relative_path).resolve()
            if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
                return self._send(403, {"error": "forbidden"})
            ctype = "text/plain"
            if str(file_path).endswith(".css"):
                ctype = "text/css"
            if str(file_path).endswith(".js"):
                ctype = "application/javascript"
            return self._serve_file(file_path, ctype)

        conn = get_conn()
        cur = conn.cursor()

        if path == "/api/dashboard":
            active = cur.execute("SELECT COUNT(*) FROM clients WHERE status='active'").fetchone()[0]
            mrr = cur.execute("SELECT COALESCE(SUM(recurring_fee),0) FROM clients WHERE status='active'").fetchone()[0]
            overdue = cur.execute("SELECT COUNT(*) FROM payments WHERE status='overdue'").fetchone()[0]
            overdue_total = cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='overdue'").fetchone()[0]
            month = date.today().strftime("%Y-%m")
            cancelled = cur.execute(
                "SELECT COUNT(*) FROM clients WHERE status='cancelled' AND substr(contract_end,1,7)=?", (month,)
            ).fetchone()[0]
            total = cur.execute("SELECT COUNT(*) FROM clients").fetchone()[0] or 1
            conn.close()
            return self._send(
                200,
                {
                    "mrr": mrr,
                    "active_clients": active,
                    "overdue_count": overdue,
                    "overdue_total": overdue_total,
                    "churn": round(cancelled / total * 100, 2),
                },
            )

        if path == "/api/clients":
            q = parse_qs(parsed.query).get("q", [""])[0].strip()
            if q:
                like = f"%{q}%"
                rows = cur.execute(
                    "SELECT * FROM clients WHERE name LIKE ? OR company LIKE ? OR email LIKE ? ORDER BY name",
                    (like, like, like),
                ).fetchall()
            else:
                rows = cur.execute("SELECT * FROM clients ORDER BY name").fetchall()
            conn.close()
            return self._send(200, [dict(r) for r in rows])

        if path.startswith("/api/clients/"):
            client_id = to_int(path.split("/")[-1])
            if client_id is None:
                conn.close()
                return self._send(400, {"error": "invalid client id"})
            client = cur.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            if not client:
                conn.close()
                return self._send(404, {"error": "not found"})
            interactions = [
                dict(r)
                for r in cur.execute(
                    "SELECT id,interaction_type as type,summary,created_at FROM interactions WHERE client_id=? ORDER BY created_at DESC",
                    (client_id,),
                ).fetchall()
            ]
            tasks = [dict(r) for r in cur.execute("SELECT * FROM tasks WHERE client_id=?", (client_id,)).fetchall()]
            payments = [
                dict(r)
                for r in cur.execute(
                    "SELECT * FROM payments WHERE client_id=? ORDER BY reference_month DESC", (client_id,)
                ).fetchall()
            ]
            conn.close()
            payload = dict(client)
            payload["interactions"] = interactions
            payload["tasks"] = tasks
            payload["payments"] = payments
            return self._send(200, payload)

        if path == "/api/interactions":
            limit = to_int(parse_qs(parsed.query).get("limit", ["20"])[0], 20)
            limit = max(1, min(limit, 100))
            rows = cur.execute(
                """
                SELECT i.id, i.interaction_type as type, i.summary, i.created_at, c.name as client_name
                FROM interactions i
                JOIN clients c ON c.id = i.client_id
                ORDER BY i.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            return self._send(200, [dict(r) for r in rows])

        if path == "/api/tasks":
            rows = cur.execute(
                "SELECT t.*, c.name as client_name FROM tasks t LEFT JOIN clients c ON c.id=t.client_id ORDER BY done ASC, due_date ASC"
            ).fetchall()
            conn.close()
            return self._send(200, [dict(r) for r in rows])

        if path == "/api/deals":
            rows = cur.execute("SELECT id,title,value,client_name,stage FROM deals ORDER BY created_at DESC").fetchall()
            conn.close()
            return self._send(200, [dict(r) for r in rows])

        conn.close()
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._json()
        conn = get_conn()
        cur = conn.cursor()

        if path == "/api/clients":
            cur.execute(
                "INSERT INTO clients(name,company,email,phone,recurring_fee,status,contract_start,contract_end,notes) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    data["name"],
                    data["company"],
                    data["email"],
                    data["phone"],
                    float(data.get("recurring_fee", 0)),
                    data.get("status", "active"),
                    data.get("contract_start"),
                    data.get("contract_end"),
                    data.get("notes"),
                ),
            )
            conn.commit()
            conn.close()
            return self._send(201, {"id": cur.lastrowid})

        if path == "/api/interactions":
            cur.execute(
                "INSERT INTO interactions(client_id,interaction_type,summary,created_at) VALUES (?,?,?,?)",
                (data["client_id"], data["type"], data["summary"], datetime.now().isoformat(timespec="minutes")),
            )
            conn.commit()
            conn.close()
            return self._send(201, {"id": cur.lastrowid})

        if path == "/api/tasks":
            cur.execute(
                "INSERT INTO tasks(client_id,title,assignee,priority,due_date) VALUES (?,?,?,?,?)",
                (data.get("client_id"), data["title"], data["assignee"], data.get("priority", "media"), data.get("due_date")),
            )
            conn.commit()
            conn.close()
            return self._send(201, {"id": cur.lastrowid})

        if path == "/api/payments":
            cur.execute(
                "INSERT INTO payments(client_id,reference_month,amount,status,paid_at) VALUES (?,?,?,?,?)",
                (data["client_id"], data["reference_month"], data["amount"], data.get("status", "pending"), data.get("paid_at")),
            )
            conn.commit()
            conn.close()
            return self._send(201, {"id": cur.lastrowid})

        if path == "/api/deals":
            cur.execute(
                "INSERT INTO deals(title,value,client_name,stage,created_at) VALUES (?,?,?,?,?)",
                (data["title"], data.get("value", 0), data["client_name"], data.get("stage", "lead"), datetime.now().isoformat(timespec="minutes")),
            )
            conn.commit()
            conn.close()
            return self._send(201, {"id": cur.lastrowid})

        conn.close()
        return self._send(404, {"error": "not found"})

    def do_PATCH(self):
        path = urlparse(self.path).path
        data = self._json()
        conn = get_conn()
        cur = conn.cursor()

        if path.startswith("/api/tasks/"):
            tid = to_int(path.split("/")[-1])
            if tid is None:
                conn.close()
                return self._send(400, {"error": "invalid task id"})
            if "done" in data:
                cur.execute("UPDATE tasks SET done=? WHERE id=?", (1 if data["done"] else 0, tid))
            if "priority" in data:
                cur.execute("UPDATE tasks SET priority=? WHERE id=?", (data["priority"], tid))
            conn.commit()
            conn.close()
            return self._send(200, {"ok": True})

        if path.startswith("/api/deals/") and path.endswith("/stage"):
            did = to_int(path.split("/")[3])
            if did is None:
                conn.close()
                return self._send(400, {"error": "invalid deal id"})
            cur.execute("UPDATE deals SET stage=? WHERE id=?", (data["stage"], did))
            conn.commit()
            conn.close()
            return self._send(200, {"ok": True})

        conn.close()
        return self._send(404, {"error": "not found"})


def parse_args():
    parser = argparse.ArgumentParser(description="CRM Natividade Digital")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Host para bind (padrão: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")), help="Porta HTTP (padrão: 5000)")
    parser.add_argument("--no-seed", action="store_true", help="Não inserir dados de exemplo")
    return parser.parse_args()


def main():
    args = parse_args()
    init_db(seed=not args.no_seed)
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"[ERRO] Não foi possível iniciar em {args.host}:{args.port} -> {exc}")
        print("Dica: tente outra porta, exemplo: python3 app.py --port 5001")
        raise SystemExit(1)

    print(f"Servidor iniciado em http://127.0.0.1:{args.port} (bind {args.host}:{args.port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
