import sys
from datetime import date, timedelta
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from scripts.prepare_environment import ensure_environment  # noqa: E402

ensure_environment()

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.database import fetch_all, fetch_one, transaction  # noqa: E402

SAMPLE_FARMERS = (
    ("SAMPLE-FARMER-01", "Demo Farmer 01", "Annapuram", "9876500101"),
    ("SAMPLE-FARMER-02", "Demo Farmer 02", "Kothuru", "9876500102"),
    ("SAMPLE-FARMER-03", "Demo Farmer 03", "Mamidipalli", "9876500103"),
    ("SAMPLE-FARMER-04", "Demo Farmer 04", "Ravipadu", "9876500104"),
    ("SAMPLE-FARMER-05", "Demo Farmer 05", "Chandramouli Nagar", "9876500105"),
    ("SAMPLE-FARMER-06", "Demo Farmer 06", "Annapuram", "9876500106"),
    ("SAMPLE-FARMER-07", "Demo Farmer 07", "Kothuru", "9876500107"),
    ("SAMPLE-FARMER-08", "Demo Farmer 08", "Mamidipalli", "9876500108"),
    ("SAMPLE-FARMER-09", "Demo Farmer 09", "Ravipadu", "9876500109"),
    ("SAMPLE-FARMER-10", "Demo Farmer 10", "Chandramouli Nagar", "9876500110"),
)

SAMPLE_TRAINERS = (
    ("SAMPLE-TRAINER-01", "Demo Trainer 01", "Soil health and nutrient management", "9876500201"),
    ("SAMPLE-TRAINER-02", "Demo Trainer 02", "Water-efficient irrigation", "9876500202"),
    ("SAMPLE-TRAINER-03", "Demo Trainer 03", "Integrated pest management", "9876500203"),
)

SAMPLE_PROGRAMS = (
    ("Modern Farming Techniques", "Farm technology", "Foundation", "Practical methods for improving farm planning and crop management.", "Apply improved crop planning and field practices.", "2 days"),
    ("Soil Health Management", "Soil science", "Intermediate", "Learn soil sampling, organic matter management and balanced nutrient use.", "Interpret soil health indicators and plan soil amendments.", "2 days"),
    ("Organic Farming", "Sustainable agriculture", "Foundation", "Explore composting, biological inputs and organic crop production practices.", "Prepare an organic input plan and maintain field records.", "3 days"),
    ("Water Management and Irrigation", "Water management", "Intermediate", "Compare irrigation methods and plan efficient water use for crops.", "Schedule irrigation using crop and field conditions.", "2 days"),
    ("Integrated Pest Management", "Crop protection", "Advanced", "Use monitoring, prevention and integrated controls to manage crop pests.", "Identify pest thresholds and select appropriate controls.", "2 days"),
)


class APIClient:
    def __init__(self, client, user_id):
        self.client = client
        self.csrf = "demo-data-seed-csrf-token"
        with client.session_transaction() as browser_session:
            browser_session["user_id"] = user_id
            browser_session["csrf_token"] = self.csrf
            browser_session.permanent = True

    def request(self, method, path, body=None, expected=(200, 201)):
        headers = {}
        if method not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self.csrf
        response = self.client.open(path, method=method, json=body, headers=headers)
        if response.status_code not in expected:
            payload = response.get_json(silent=True) or {}
            error = payload.get("error", {}).get("message", "The API returned an unexpected response.")
            raise RuntimeError(f"{method} {path} returned {response.status_code}: {error}")
        return response.get_json(silent=True) or {}


def seed_demo_data(app):
    admin = fetch_one("SELECT id FROM users WHERE username='demo.admin' AND role='admin' AND account_status='active'")
    if not admin:
        raise RuntimeError("An active demo.admin account is required. Create it using the secure demo account setup first.")
    demo_farmer = fetch_one("SELECT id FROM users WHERE username='demo.farmer' AND role='farmer' AND account_status='active'")
    demo_trainer = fetch_one("SELECT id FROM users WHERE username='demo.trainer' AND role='trainer' AND account_status='active'")
    if not demo_farmer or not demo_trainer:
        raise RuntimeError("Active demo.farmer and demo.trainer accounts are required.")
    farmer_profile = fetch_one("SELECT id FROM farmers WHERE user_id=%s AND record_status='active'", (demo_farmer["id"],))
    trainer_profile = fetch_one("SELECT id FROM trainers WHERE user_id=%s AND record_status='active'", (demo_trainer["id"],))
    if not farmer_profile or not trainer_profile:
        raise RuntimeError("The demo farmer and trainer must have active linked profiles.")

    admin_api = APIClient(app.test_client(), admin["id"])
    coordinator_id = fetch_one(
        "SELECT id FROM users WHERE username='demo.coordinator' AND role='coordinator' AND account_status='active'"
    )["id"]
    coordinator_api = APIClient(app.test_client(), coordinator_id)
    trainer_api = APIClient(app.test_client(), demo_trainer["id"])

    before = {
        "farmers": fetch_one("SELECT COUNT(*) AS n FROM farmers WHERE farmer_id LIKE 'SAMPLE-FARMER-%'")["n"],
        "trainers": fetch_one("SELECT COUNT(*) AS n FROM trainers WHERE trainer_id LIKE 'SAMPLE-TRAINER-%'")["n"],
        "programs": fetch_one("SELECT COUNT(*) AS n FROM training_programs WHERE program_name LIKE 'Demonstration: %'")["n"],
        "sessions": fetch_one("SELECT COUNT(*) AS n FROM training_sessions WHERE session_details LIKE 'AgriLearn demo seed v1:%'")["n"],
    }

    for farmer_id, name, village, phone in SAMPLE_FARMERS:
        if fetch_one("SELECT id FROM farmers WHERE farmer_id=%s", (farmer_id,)):
            continue
        admin_api.request("POST", "/api/farmers", {
            "farmer_id": farmer_id,
            "full_name": name,
            "village": village,
            "phone": phone,
            "email": f"{farmer_id.lower()}@example.com",
        })

    for trainer_id, name, specialization, phone in SAMPLE_TRAINERS:
        if fetch_one("SELECT id FROM trainers WHERE trainer_id=%s", (trainer_id,)):
            continue
        admin_api.request("POST", "/api/trainers", {
            "trainer_id": trainer_id,
            "full_name": name,
            "specialization": specialization,
            "phone": phone,
            "email": f"{trainer_id.lower()}@example.com",
        })

    farmer_profiles = {
        row["farmer_id"]: row["id"]
        for row in fetch_all(
            "SELECT id,farmer_id FROM farmers WHERE farmer_id LIKE 'SAMPLE-FARMER-%' AND record_status='active'"
        )
    }
    farmer_profiles["DEMO-FARMER"] = farmer_profile["id"]
    trainer_profiles = {
        row["trainer_id"]: row["id"]
        for row in fetch_all(
            "SELECT id,trainer_id FROM trainers WHERE trainer_id LIKE 'SAMPLE-TRAINER-%' AND record_status='active'"
        )
    }
    if len(farmer_profiles) < 11 or len(trainer_profiles) < 3:
        raise RuntimeError("Required active farmer or trainer profiles are missing after creation.")

    program_ids = {}
    for title, category, level, description, objectives, duration in SAMPLE_PROGRAMS:
        name = f"Demonstration: {title}"
        existing = fetch_one("SELECT id FROM training_programs WHERE program_name=%s", (name,))
        if existing:
            program_ids[name] = existing["id"]
            continue
        result = admin_api.request("POST", "/api/programs", {
            "program_name": name,
            "category": category,
            "level": level,
            "description": description,
            "objectives": objectives,
            "duration": duration,
            "status": "active",
        })
        program_ids[name] = result["data"]["id"]

    trainers_by_index = [
        trainer_profile["id"],
        trainer_profiles["SAMPLE-TRAINER-01"],
        trainer_profiles["SAMPLE-TRAINER-02"],
        trainer_profiles["SAMPLE-TRAINER-03"],
        trainer_profile["id"],
    ]
    session_ids = {}
    for program_index, (program_name, program_id) in enumerate(program_ids.items()):
        selected = [farmer_profiles["DEMO-FARMER"]]
        selected.extend(
            farmer_profiles[f"SAMPLE-FARMER-{(program_index * 2 + offset) % 10 + 1:02d}"]
            for offset in range(4)
        )
        trainer_id = trainers_by_index[program_index]
        for session_index, (delta, status) in enumerate(((-2, "completed"), (7, "scheduled"))):
            marker = f"AgriLearn demo seed v1:{program_id}:{session_index}"
            existing = fetch_one(
                "SELECT id FROM training_sessions WHERE session_details=%s",
                (marker,),
            )
            if existing:
                session_ids[(program_id, session_index)] = existing["id"]
                continue
            result = coordinator_api.request("POST", "/api/sessions", {
                "program_id": program_id,
                "trainer_id": trainer_id,
                "session_date": (date.today() + timedelta(days=delta + program_index)).isoformat(),
                "start_time": "09:00",
                "end_time": "12:00",
                "location": f"Demonstration Training Centre {program_index + 1}",
                "session_details": marker,
                "status": status,
                "farmer_ids": selected,
            })
            session_ids[(program_id, session_index)] = result["data"]["id"]

        for farmer_id in selected:
            if fetch_one("SELECT id FROM program_farmers WHERE program_id=%s AND farmer_id=%s", (program_id, farmer_id)):
                continue
            coordinator_api.request("POST", "/api/enrollments", {
                "program_id": program_id,
                "farmer_id": farmer_id,
                "participation_status": "enrolled",
            })

        completed_session = session_ids[(program_id, 0)]
        for offset, farmer_id in enumerate(selected):
            status = "absent" if offset == 3 else "present"
            if not fetch_one(
                "SELECT id FROM attendance WHERE session_id=%s AND farmer_id=%s",
                (completed_session, farmer_id),
            ):
                attendance_api = trainer_api if trainer_id == trainer_profile["id"] else admin_api
                attendance_api.request("POST", "/api/attendance", {
                    "session_id": completed_session,
                    "farmer_id": farmer_id,
                    "attendance_status": status,
                })

            existing_progress = fetch_one(
                "SELECT id FROM training_progress WHERE farmer_id=%s AND program_id=%s",
                (farmer_id, program_id),
            )
            progress = {
                "farmer_id": farmer_id,
                "program_id": program_id,
                "progress_details": "Demonstration progress record for training workflow practice.",
                "progress_percent": 100 if offset == 0 else 50,
                "completion_status": "completed" if offset == 0 else "in_progress",
                "result": "Demonstration completion" if offset == 0 else "In progress",
            }
            if existing_progress:
                continue
            admin_api.request("POST", "/api/progress", progress)

    after = {
        "farmers": fetch_one("SELECT COUNT(*) AS n FROM farmers WHERE farmer_id LIKE 'SAMPLE-FARMER-%'")["n"],
        "trainers": fetch_one("SELECT COUNT(*) AS n FROM trainers WHERE trainer_id LIKE 'SAMPLE-TRAINER-%'")["n"],
        "programs": fetch_one("SELECT COUNT(*) AS n FROM training_programs WHERE program_name LIKE 'Demonstration: %'")["n"],
        "sessions": fetch_one("SELECT COUNT(*) AS n FROM training_sessions WHERE session_details LIKE 'AgriLearn demo seed v1:%'")["n"],
        "enrollments": fetch_one("SELECT COUNT(*) AS n FROM program_farmers WHERE program_id IN (SELECT id FROM training_programs WHERE program_name LIKE 'Demonstration: %')")["n"],
        "attendance": fetch_one("SELECT COUNT(*) AS n FROM attendance WHERE session_id IN (SELECT id FROM training_sessions WHERE session_details LIKE 'AgriLearn demo seed v1:%')")["n"],
        "progress": fetch_one("SELECT COUNT(*) AS n FROM training_progress WHERE program_id IN (SELECT id FROM training_programs WHERE program_name LIKE 'Demonstration: %')")["n"],
    }
    for key in ("farmers", "trainers", "programs", "sessions"):
        if after[key] < before[key]:
            raise RuntimeError(f"Existing demonstration data unexpectedly decreased for {key}.")
    return before, after


def main():
    try:
        Config.validate()
    except RuntimeError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1
    app = create_app()
    try:
        with app.app_context():
            before, after = seed_demo_data(app)
    except Exception as error:
        print(f"Sample data setup failed: {error}", file=sys.stderr)
        return 1

    print("Sample-data counts in MySQL (no existing records were deleted):")
    for key, count in after.items():
        print(f"{key}: {count}")
    print("The seed is idempotent; run it again to verify it does not duplicate records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
