"""HTTP and WebSocket contract checks for the local demo service."""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def test_session_controls_stream_and_export(self) -> None:
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").json()["status"], "ok")
            started = client.post("/api/session/start")
            self.assertEqual(started.status_code, 200)
            self.assertTrue(started.json()["running"])
            with client.websocket_connect("/ws/telemetry") as socket:
                frame = socket.receive_json()
                self.assertEqual(frame["mode"], "simulation")
                self.assertEqual(frame["exercise"], "biceps_curl")
                self.assertIn("compensation_risk", frame["ai"])
                self.assertEqual(len(frame["range_doppler"]), 18)
            stopped = client.post("/api/session/stop")
            self.assertFalse(stopped.json()["running"])
            csv_response = client.get("/api/session/export.csv")
            self.assertEqual(csv_response.status_code, 200)
            self.assertTrue(csv_response.text.startswith("timestamp,rep_count,movement_signal"))
            reset = client.post("/api/session/reset")
            self.assertEqual(reset.json()["movement"]["rep_count"], 0)


if __name__ == "__main__":
    unittest.main()
