import json
import subprocess
import time
import unittest
from urllib import request


class ApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 5055
        cls.proc = subprocess.Popen(
            ["python3", "app.py", "--port", str(cls.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with request.urlopen(f"http://127.0.0.1:{cls.port}/health", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    def _get_json(self, path):
        with request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode())

    def _post_json(self, path, payload):
        data = json.dumps(payload).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=3) as resp:
            self.assertIn(resp.status, (200, 201))
            return json.loads(resp.read().decode())

    def test_health_and_dashboard(self):
        health = self._get_json("/health")
        self.assertEqual(health["status"], "ok")
        dash = self._get_json("/api/dashboard")
        self.assertIn("mrr", dash)
        self.assertIn("overdue_total", dash)

    def test_create_client_and_fetch(self):
        created = self._post_json(
            "/api/clients",
            {
                "name": "Teste QA",
                "company": "Empresa QA",
                "email": "qa@example.com",
                "phone": "11999999999",
                "recurring_fee": 999,
            },
        )
        self.assertIn("id", created)

        clients = self._get_json("/api/clients?q=Teste%20QA")
        self.assertTrue(any(c["name"] == "Teste QA" for c in clients))


if __name__ == "__main__":
    unittest.main()
