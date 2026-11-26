import os
import sys
import unittest
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
import mysql.connector  # noqa: E402


@unittest.skipUnless(
    os.getenv("AGRILEARN_RUN_MYSQL_TESTS") == "1",
    "Set AGRILEARN_RUN_MYSQL_TESTS=1 to run read-only MySQL acceptance checks.",
)
class LiveMySQLAcceptanceTests(unittest.TestCase):
    DATA_TABLES = (
        "users",
        "farmers",
        "trainers",
        "training_programs",
        "training_sessions",
        "program_farmers",
        "attendance",
        "training_progress",
    )

    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True})
        cls.app.config["DB_CONFIG"] = Config.DB_CONFIG
        with mysql.connector.connect(**Config.DB_CONFIG) as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, role FROM users
                     WHERE username IN (
                       'demo.admin','demo.coordinator','demo.trainer',
                       'demo.management','demo.farmer'
                     ) AND account_status='active'"""
            )
            cls.accounts = {row["role"]: row["id"] for row in cursor.fetchall()}
            cursor.close()
        cls.record_counts_before = cls.record_counts()

    @classmethod
    def record_counts(cls):
        counts = {}
        with mysql.connector.connect(**Config.DB_CONFIG) as connection:
            cursor = connection.cursor()
            for table in cls.DATA_TABLES:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                counts[table] = cursor.fetchone()[0]
            cursor.close()
        return counts

    def client_as(self, role):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = self.accounts[role]
        return client

    def test_all_five_database_backed_dashboards(self):
        routes = {
            "admin": "/api/dashboard/admin",
            "coordinator": "/api/dashboard/coordinator",
            "trainer": "/api/dashboard/trainer",
            "management": "/api/dashboard/management",
            "farmer": "/api/dashboard/farmer",
        }
        self.assertEqual(set(self.accounts), set(routes))
        for role, route in routes.items():
            with self.subTest(role=role):
                response = self.client_as(role).get(route)
                self.assertEqual(response.status_code, 200, response.get_json())

    def test_existing_read_api_modules_match_role_permissions(self):
        roles = ("admin", "coordinator", "trainer", "management", "farmer")
        shared_resources = (
            "/api/farmers",
            "/api/programs",
            "/api/sessions",
            "/api/enrollments",
            "/api/attendance",
            "/api/progress",
            "/api/auth/me",
        )
        for role in roles:
            client = self.client_as(role)
            for path in shared_resources:
                with self.subTest(role=role, path=path):
                    self.assertEqual(client.get(path).status_code, 200)

            expected_trainer_status = 403 if role == "farmer" else 200
            self.assertEqual(client.get("/api/trainers").status_code, expected_trainer_status)
            expected_user_status = 200 if role == "admin" else 403
            self.assertEqual(client.get("/api/users").status_code, expected_user_status)
            expected_report_status = 200 if role in {"admin", "coordinator", "management"} else 403
            self.assertEqual(client.get("/api/reports/farmers").status_code, expected_report_status)

    def test_farmer_sessions_are_enrolled_only_and_include_authorized_trainer_names(self):
        farmer_id = self.accounts["farmer"]
        with mysql.connector.connect(**Config.DB_CONFIG) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """SELECT DISTINCT s.id
                     FROM training_sessions s
                     JOIN program_farmers pf ON pf.program_id=s.program_id
                     JOIN farmers f ON f.id=pf.farmer_id
                    WHERE f.user_id=%s AND f.record_status='active'
                      AND pf.participation_status<>'withdrawn'
                      AND s.status<>'cancelled'""",
                (farmer_id,),
            )
            expected_ids = {row[0] for row in cursor.fetchall()}
            cursor.close()

        client = self.client_as("farmer")
        first = client.get("/api/sessions?per_page=100")
        second = client.get("/api/sessions?per_page=100")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        sessions = first.get_json()["data"]
        self.assertEqual(
            {row["id"] for row in sessions},
            expected_ids,
            "Farmers should only receive sessions for their own active enrollments.",
        )
        self.assertEqual(
            [row["id"] for row in sessions],
            [row["id"] for row in second.get_json()["data"]],
            "Repeated read-only requests should return persisted database records.",
        )
        self.assertTrue(all(row["trainer_name"] for row in sessions))
        self.assertEqual(client.get("/api/trainers").status_code, 403)

    def test_role_restricted_endpoints_remain_protected(self):
        self.assertEqual(self.client_as("farmer").get("/api/users").status_code, 403)
        self.assertEqual(self.client_as("trainer").get("/api/reports/farmers").status_code, 403)
        self.assertEqual(self.client_as("management").get("/api/reports/farmers").status_code, 200)

    def test_read_only_acceptance_checks_do_not_change_database_records(self):
        self.assertEqual(self.record_counts(), self.record_counts_before)


if __name__ == "__main__":
    unittest.main()
