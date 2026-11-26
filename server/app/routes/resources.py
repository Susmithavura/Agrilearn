from datetime import date, time
import re

from flask import g, jsonify, request
from werkzeug.security import generate_password_hash

from ..database import fetch_all, fetch_one, transaction
from ..routes import api
from ..security import (
    api_error,
    enum_value,
    get_json,
    login_required,
    optional_text,
    positive_id,
    required_text,
    roles_required,
)

USER_ROLES = ("admin", "coordinator", "trainer", "farmer", "management")
RESOURCE_ROLES = ("admin", "coordinator")
MUTABLE_ROLES = ("admin", "coordinator", "trainer")
PROGRAM_STATUS = ("active", "draft", "archived")
ATTENDANCE_STATUS = ("present", "absent")
ENROLLMENT_STATUS = ("enrolled", "active", "completed", "withdrawn")
COMPLETION_STATUS = ("not_started", "in_progress", "completed")


def _page_params():
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = min(100, max(1, int(request.args.get("per_page", "25"))))
    except ValueError:
        raise ValueError("page and per_page must be integers.") from None
    return page, per_page, (page - 1) * per_page


def _list_response(query, params=()):
    page, per_page, offset = _page_params()
    rows = fetch_all(f"{query} LIMIT %s OFFSET %s", (*params, per_page, offset))
    return jsonify(data=rows, meta={"page": page, "per_page": per_page, "count": len(rows)})


def _record_or_404(query, record_id, params=()):
    record = fetch_one(query, (*params, record_id))
    if not record:
        return None, (jsonify(error={"code": "not_found", "message": "The requested record was not found."}), 404)
    return record, None


def _entity_id(value, label):
    try:
        return positive_id(value, label)
    except ValueError as error:
        raise ValueError(str(error)) from None


def _date(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must use YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} must use YYYY-MM-DD format.") from None


def _time(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must use HH:MM format.")
    try:
        return time.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} must use HH:MM format.") from None


def _clean_email(value, required=False):
    if value is None or value == "":
        if required:
            raise ValueError("Email address is required.")
        return None
    if not isinstance(value, str):
        raise ValueError("Email address must be text.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("Enter a valid email address.")
    return value


def _clean_phone(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9+() .-]{7,32}", value.strip()):
        raise ValueError("Enter a valid phone number.")
    return value.strip()


@api.post("/users")
@roles_required("admin")
def create_user():
    try:
        body = get_json()
        full_name = required_text(body, "full_name", "Full name", 160)
        username = required_text(body, "username", "Username", 80)
        password = body.get("password")
        if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
            return api_error("Password must contain at least 12 characters.", 400)
        role = enum_value(body, "role", USER_ROLES, "Role")
        email = _clean_email(body.get("email"))
        phone = _clean_phone(body["phone"]) if body.get("phone") else None
        status = enum_value(body, "account_status", ("active", "inactive"), "Account status", "active")
        language = enum_value(body, "language_preference", ("en", "te", "hi"), "Language preference", "en")
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO users
                   (full_name, username, password_hash, role, email, phone, account_status, language_preference)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (full_name, username, generate_password_hash(password), role, email, phone, status, language),
            )
            user_id = cursor.lastrowid
            if role == "farmer":
                farmer_id = required_text(body, "farmer_id", "Farmer ID", 40)
                village = required_text(body, "village", "Village", 160)
                farmer_phone = _clean_phone(body.get("farmer_phone") or phone or "")
                cursor.execute(
                    """INSERT INTO farmers (farmer_id, user_id, full_name, village, phone, email)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (farmer_id, user_id, full_name, village, farmer_phone, email),
                )
            elif role == "trainer":
                trainer_id = required_text(body, "trainer_id", "Trainer ID", 40)
                specialization = required_text(body, "specialization", "Specialization", 255)
                trainer_phone = _clean_phone(body.get("trainer_phone") or phone or "")
                cursor.execute(
                    """INSERT INTO trainers (trainer_id, user_id, full_name, specialization, phone, email)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (trainer_id, user_id, full_name, specialization, trainer_phone, email),
                )
            cursor.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id) VALUES (%s, 'create', 'user', %s)", (g.user["id"], user_id))
            cursor.close()
        created = fetch_one(
            """SELECT id, full_name, username, role, email, phone, account_status,
                      language_preference, created_at, updated_at FROM users WHERE id = %s""",
            (user_id,),
        )
        return jsonify(data=created), 201
    except ValueError as error:
        return api_error(str(error), 400)


@api.get("/users")
@roles_required("admin")
def list_users():
    where, params = _search_filter("users", ("full_name", "username", "email"), {"role", "account_status"})
    return _list_response(
        f"""SELECT id, full_name, username, role, email, phone, account_status,
                    language_preference, created_at, updated_at FROM users{where} ORDER BY id DESC""",
        params,
    )


@api.get("/users/<int:record_id>")
@roles_required("admin")
def get_user(record_id):
    return _get("SELECT id, full_name, username, role, email, phone, account_status, language_preference, created_at, updated_at FROM users WHERE id = %s", record_id)


@api.put("/users/<int:record_id>")
@roles_required("admin")
def update_user(record_id):
    try:
        body = get_json()
        full_name = required_text(body, "full_name", "Full name", 160)
        email = _clean_email(body.get("email"))
        phone = _clean_phone(body["phone"]) if body.get("phone") else None
        role = enum_value(body, "role", USER_ROLES, "Role")
        language = enum_value(body, "language_preference", ("en", "te", "hi"), "Language preference", "en")
        existing = fetch_one("SELECT id,role FROM users WHERE id=%s", (record_id,))
        if not existing:
            return _not_found()
        if role != existing["role"]:
            return api_error("An account's role cannot be changed after creation. Create a correctly linked account instead.", 409)
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET full_name=%s, email=%s, phone=%s, role=%s, language_preference=%s WHERE id=%s", (full_name, email, phone, role, language, record_id))
            cursor.execute("UPDATE farmers SET full_name=%s,phone=COALESCE(%s,phone),email=%s WHERE user_id=%s", (full_name, phone, email, record_id))
            cursor.execute("UPDATE trainers SET full_name=%s,phone=COALESCE(%s,phone),email=%s WHERE user_id=%s", (full_name, phone, email, record_id))
            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM users WHERE id=%s", (record_id,))
                if cursor.fetchone() is None:
                    return _not_found()
            cursor.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id) VALUES (%s, 'update', 'user', %s)", (g.user["id"], record_id))
            cursor.close()
        return _get("SELECT id, full_name, username, role, email, phone, account_status, language_preference, created_at, updated_at FROM users WHERE id=%s", record_id)
    except ValueError as error:
        return api_error(str(error), 400)


@api.patch("/users/<int:record_id>/status")
@roles_required("admin")
def update_user_status(record_id):
    try:
        body = get_json()
        status = enum_value(body, "account_status", ("active", "inactive"), "Account status")
        if record_id == g.user["id"] and status == "inactive":
            return api_error("You cannot deactivate your own administrator account.", 400)
        target = fetch_one("SELECT role,account_status FROM users WHERE id=%s", (record_id,))
        if not target:
            return _not_found()
        if target["role"] == "admin" and target["account_status"] == "active" and status == "inactive":
            active_admins = fetch_one("SELECT COUNT(*) AS total FROM users WHERE role='admin' AND account_status='active'")["total"]
            if active_admins <= 1:
                return api_error("The last active administrator account cannot be deactivated.", 409)
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET account_status=%s WHERE id=%s", (status, record_id))
            cursor.execute("UPDATE farmers SET record_status=%s WHERE user_id=%s", (status, record_id))
            cursor.execute("UPDATE trainers SET record_status=%s WHERE user_id=%s", (status, record_id))
            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM users WHERE id=%s", (record_id,))
                if cursor.fetchone() is None:
                    return _not_found()
            cursor.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id) VALUES (%s, 'status_change', 'user', %s)", (g.user["id"], record_id))
            cursor.close()
        return _get("SELECT id, full_name, username, role, email, phone, account_status, language_preference, created_at, updated_at FROM users WHERE id=%s", record_id)
    except ValueError as error:
        return api_error(str(error), 400)


def _search_filter(table, columns, allowed_filters):
    clauses = []
    params = []
    search = request.args.get("q", "").strip()
    if search:
        clauses.append("(" + " OR ".join(f"{column} LIKE %s" for column in columns) + ")")
        params.extend([f"%{search}%"] * len(columns))
    for key in allowed_filters:
        value = request.args.get(key)
        if value:
            clauses.append(f"{key} = %s")
            params.append(value)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _get(query, record_id, params=()):
    row, error = _record_or_404(query, record_id, params)
    return error or jsonify(data=row)


def _not_found():
    return jsonify(error={"code": "not_found", "message": "The requested record was not found."}), 404


def _json_body():
    try:
        return get_json(), None
    except ValueError as error:
        return None, api_error(str(error), 400)


def _profile_list(kind, query, searchable, filters):
    where, params = _search_filter(kind, searchable, filters)
    return _list_response(f"{query}{where} ORDER BY id DESC", params)


@api.post("/farmers")
@roles_required("admin", "coordinator")
def create_farmer():
    body, error = _json_body()
    if error:
        return error
    try:
        farmer_id = required_text(body, "farmer_id", "Farmer ID", 40)
        full_name = required_text(body, "full_name", "Farmer name", 160)
        village = required_text(body, "village", "Village", 160)
        phone = _clean_phone(body.get("phone"))
        email = _clean_email(body.get("email"))
        user_id = positive_id(body["user_id"], "user id") if body.get("user_id") else None
        with transaction() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT id FROM users WHERE id=%s AND role='farmer'", (user_id,))
                if not cursor.fetchone():
                    return api_error("The linked account must exist and have the farmer role.", 400)
            cursor.execute("INSERT INTO farmers (farmer_id,user_id,full_name,village,phone,email) VALUES (%s,%s,%s,%s,%s,%s)", (farmer_id,user_id,full_name,village,phone,email))
            record_id = cursor.lastrowid
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'create','farmer',%s)", (g.user["id"],record_id))
            cursor.close()
        return _get(_FARMER_SELECT + " WHERE f.id=%s", record_id)
    except ValueError as exc:
        return api_error(str(exc), 400)


_FARMER_SELECT = """SELECT f.id, f.farmer_id, f.user_id, f.full_name AS name, f.village,
                           f.phone, f.email, f.record_status AS status, f.created_at, f.updated_at
                      FROM farmers f"""


def _visible_farmers_query():
    if g.user["role"] == "farmer":
        return _FARMER_SELECT + " WHERE f.user_id=%s AND f.record_status='active'", (g.user["id"],)
    if g.user["role"] == "trainer":
        return _FARMER_SELECT + """ WHERE EXISTS (
            SELECT 1 FROM program_farmers pf
            JOIN training_sessions ts ON ts.program_id=pf.program_id
            JOIN trainers t ON t.id=ts.trainer_id
            WHERE pf.farmer_id=f.id AND t.user_id=%s) AND f.record_status='active'""", (g.user["id"],)
    return _FARMER_SELECT + " WHERE f.record_status='active'", ()


@api.get("/farmers")
@roles_required("admin", "coordinator", "trainer", "management", "farmer")
def list_farmers():
    base, base_params = _visible_farmers_query()
    where, params = _search_filter("farmers", ("f.full_name", "f.farmer_id", "f.village", "f.phone"), {"village"})
    return _list_response(base + (where if " WHERE " not in base else (" AND " + where[7:] if where else "")) + " ORDER BY f.id DESC", (*base_params, *params))


@api.get("/farmers/<int:record_id>")
@roles_required("admin", "coordinator", "trainer", "management", "farmer")
def get_farmer(record_id):
    base, params = _visible_farmers_query()
    condition = " AND f.id=%s" if " WHERE " in base else " WHERE f.id=%s"
    return _get(base + condition, record_id, params)


@api.put("/farmers/<int:record_id>")
@roles_required("admin", "coordinator")
def update_farmer(record_id):
    body, error = _json_body()
    if error:
        return error
    try:
        full_name = required_text(body, "full_name", "Farmer name", 160)
        village = required_text(body, "village", "Village", 160)
        phone = _clean_phone(body.get("phone"))
        email = _clean_email(body.get("email"))
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE farmers SET full_name=%s,village=%s,phone=%s,email=%s WHERE id=%s", (full_name,village,phone,email,record_id))
            if cursor.rowcount == 0 and not fetch_one("SELECT id FROM farmers WHERE id=%s", (record_id,)):
                return _not_found()
            cursor.execute("UPDATE users u JOIN farmers f ON f.user_id=u.id SET u.full_name=%s,u.phone=%s,u.email=%s WHERE f.id=%s", (full_name,phone,email,record_id))
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','farmer',%s)", (g.user["id"],record_id))
            cursor.close()
        return _get(_FARMER_SELECT + " WHERE f.id=%s", record_id)
    except ValueError as exc:
        return api_error(str(exc), 400)


@api.delete("/farmers/<int:record_id>")
@roles_required("admin", "coordinator")
def delete_farmer(record_id):
    try:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id,user_id FROM farmers WHERE id=%s FOR UPDATE", (record_id,))
            farmer = cursor.fetchone()
            if not farmer:
                return _not_found()
            if farmer[1]:
                cursor.execute("UPDATE users SET account_status='inactive' WHERE id=%s", (farmer[1],))
            cursor.execute("UPDATE farmers SET record_status='inactive' WHERE id=%s", (record_id,))
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'deactivate','farmer',%s)", (g.user["id"],record_id))
            cursor.close()
        return jsonify(data={"deactivated": True, "record_id": record_id})
    except ValueError as exc:
        return api_error(str(exc), 400)


_TRAINER_SELECT = """SELECT t.id,t.trainer_id,t.user_id,t.full_name AS name,t.specialization,
                            t.phone,t.email,t.record_status AS status,t.created_at,t.updated_at FROM trainers t"""


def _visible_trainers_query():
    if g.user["role"] == "trainer":
        return _TRAINER_SELECT + " WHERE t.user_id=%s AND t.record_status='active'", (g.user["id"],)
    return _TRAINER_SELECT + " WHERE t.record_status='active'", ()


@api.post("/trainers")
@roles_required("admin", "coordinator")
def create_trainer():
    body, error = _json_body()
    if error:
        return error
    try:
        trainer_id = required_text(body, "trainer_id", "Trainer ID", 40)
        full_name = required_text(body, "full_name", "Trainer name", 160)
        specialization = required_text(body, "specialization", "Specialization", 255)
        phone = _clean_phone(body.get("phone"))
        email = _clean_email(body.get("email"))
        user_id = positive_id(body["user_id"], "user id") if body.get("user_id") else None
        with transaction() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT id FROM users WHERE id=%s AND role='trainer'", (user_id,))
                if not cursor.fetchone():
                    return api_error("The linked account must exist and have the trainer role.", 400)
            cursor.execute("INSERT INTO trainers (trainer_id,user_id,full_name,specialization,phone,email) VALUES (%s,%s,%s,%s,%s,%s)",(trainer_id,user_id,full_name,specialization,phone,email))
            record_id = cursor.lastrowid
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'create','trainer',%s)",(g.user["id"],record_id))
            cursor.close()
        return _get(_TRAINER_SELECT + " WHERE t.id=%s", record_id)
    except ValueError as exc:
        return api_error(str(exc),400)


@api.get("/trainers")
@roles_required("admin", "coordinator", "trainer", "management")
def list_trainers():
    base, base_params = _visible_trainers_query()
    where, params = _search_filter("trainers", ("t.full_name","t.trainer_id","t.specialization","t.phone"), set())
    return _list_response(base + (where if " WHERE " not in base else (" AND " + where[7:] if where else "")) + " ORDER BY t.id DESC",(*base_params,*params))


@api.get("/trainers/<int:record_id>")
@roles_required("admin", "coordinator", "trainer", "management")
def get_trainer(record_id):
    base, params = _visible_trainers_query()
    return _get(base + (" AND " if " WHERE " in base else " WHERE ") + "t.id=%s",record_id,params)


@api.put("/trainers/<int:record_id>")
@roles_required("admin", "coordinator")
def update_trainer(record_id):
    body,error=_json_body()
    if error:return error
    try:
        full_name=required_text(body,"full_name","Trainer name",160); specialization=required_text(body,"specialization","Specialization",255)
        phone=_clean_phone(body.get("phone")); email=_clean_email(body.get("email"))
        with transaction() as conn:
            cursor=conn.cursor(); cursor.execute("UPDATE trainers SET full_name=%s,specialization=%s,phone=%s,email=%s WHERE id=%s",(full_name,specialization,phone,email,record_id))
            if cursor.rowcount==0 and not fetch_one("SELECT id FROM trainers WHERE id=%s",(record_id,)):return _not_found()
            cursor.execute("UPDATE users u JOIN trainers t ON t.user_id=u.id SET u.full_name=%s,u.phone=%s,u.email=%s WHERE t.id=%s",(full_name,phone,email,record_id))
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','trainer',%s)",(g.user["id"],record_id)); cursor.close()
        return _get(_TRAINER_SELECT+" WHERE t.id=%s",record_id)
    except ValueError as exc:return api_error(str(exc),400)


@api.delete("/trainers/<int:record_id>")
@roles_required("admin","coordinator")
def delete_trainer(record_id):
    try:
        with transaction() as conn:
            cursor=conn.cursor(); cursor.execute("SELECT id,user_id FROM trainers WHERE id=%s FOR UPDATE",(record_id,)); trainer=cursor.fetchone()
            if not trainer:return _not_found()
            cursor.execute("UPDATE trainers SET record_status='inactive' WHERE id=%s",(record_id,))
            if trainer[1]:cursor.execute("UPDATE users SET account_status='inactive' WHERE id=%s",(trainer[1],))
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'deactivate','trainer',%s)",(g.user["id"],record_id)); cursor.close()
        return jsonify(data={"deactivated":True,"record_id":record_id})
    except ValueError as exc:return api_error(str(exc),400)


_PROGRAM_SELECT = """SELECT p.id,p.program_name AS title,p.category,p.level,p.description,
                            p.objectives,p.duration,p.status,p.created_at,p.updated_at
                       FROM training_programs p"""
_SESSION_SELECT = """SELECT s.id,s.program_id,s.trainer_id,CAST(s.session_date AS CHAR) AS date,
                            CAST(s.start_time AS CHAR) AS time,
                            CAST(s.end_time AS CHAR) AS end_time,
                            s.location,s.session_details AS details,
                            s.status,s.created_at,s.updated_at,p.program_name AS program_title,
                            t.full_name AS trainer_name
                       FROM training_sessions s
                       JOIN training_programs p ON p.id=s.program_id
                       JOIN trainers t ON t.id=s.trainer_id"""


def _visible_program_query():
    if g.user["role"] == "farmer":
        return _PROGRAM_SELECT + " WHERE p.status='active'"
    if g.user["role"] == "trainer":
        return _PROGRAM_SELECT + """ WHERE EXISTS (
            SELECT 1 FROM training_sessions s JOIN trainers t ON t.id=s.trainer_id
             WHERE s.program_id=p.id AND t.user_id=%s AND s.status<>'cancelled')"""
    return _PROGRAM_SELECT


@api.post("/programs")
@roles_required("admin", "coordinator")
def create_program():
    body, error = _json_body()
    if error:
        return error
    try:
        name = required_text(body, "program_name", "Program name", 200)
        category = required_text(body, "category", "Category", 120)
        level = enum_value(body, "level", ("Foundation", "Intermediate", "Advanced"), "Level", "Foundation")
        description = required_text(body, "description", "Description", 10000)
        objectives = optional_text(body, "objectives", 10000)
        duration = required_text(body, "duration", "Duration", 80)
        status = enum_value(body, "status", PROGRAM_STATUS, "Status", "active")
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO training_programs (program_name,category,level,description,objectives,duration,status) VALUES (%s,%s,%s,%s,%s,%s,%s)", (name,category,level,description,objectives,duration,status))
            record_id = cursor.lastrowid
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'create','training_program',%s)",(g.user["id"],record_id))
            cursor.close()
        return _get(_PROGRAM_SELECT+" WHERE p.id=%s",record_id)
    except ValueError as exc:
        return api_error(str(exc),400)


@api.get("/programs")
@roles_required("admin","coordinator","trainer","farmer","management")
def list_programs():
    base=_visible_program_query()
    params=(g.user["id"],) if g.user["role"]=="trainer" else ()
    where,search_params=_search_filter("training_programs",("p.program_name","p.category","p.description"),{"status","category"})
    if " WHERE " in base and where:
        base += " AND "+where[7:]
    else:
        base += where
    return _list_response(base+" ORDER BY p.id DESC",(*params,*search_params))


@api.get("/programs/<int:record_id>")
@roles_required("admin","coordinator","trainer","farmer","management")
def get_program(record_id):
    base=_visible_program_query()
    params=(g.user["id"],) if g.user["role"]=="trainer" else ()
    if g.user["role"]=="farmer":
        base += " AND p.id=%s" if " WHERE " in base else " WHERE p.id=%s"
        row=fetch_one(base,(*params,record_id))
    else:
        row=fetch_one(base+(" AND " if " WHERE " in base else " WHERE ")+"p.id=%s",(*params,record_id))
    return (jsonify(data=row) if row else _not_found())


@api.put("/programs/<int:record_id>")
@roles_required("admin","coordinator")
def update_program(record_id):
    body,error=_json_body()
    if error:return error
    try:
        fields=(
            required_text(body,"program_name","Program name",200),
            required_text(body,"category","Category",120),
            enum_value(body,"level",("Foundation","Intermediate","Advanced"),"Level"),
            required_text(body,"description","Description",10000),
            optional_text(body,"objectives",10000),
            required_text(body,"duration","Duration",80),
            enum_value(body,"status",PROGRAM_STATUS,"Status"),
        )
        with transaction() as conn:
            cursor=conn.cursor(); cursor.execute("UPDATE training_programs SET program_name=%s,category=%s,level=%s,description=%s,objectives=%s,duration=%s,status=%s WHERE id=%s",(*fields,record_id))
            if cursor.rowcount==0 and not fetch_one("SELECT id FROM training_programs WHERE id=%s",(record_id,)):return _not_found()
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','training_program',%s)",(g.user["id"],record_id)); cursor.close()
        return _get(_PROGRAM_SELECT+" WHERE p.id=%s",record_id)
    except ValueError as exc:return api_error(str(exc),400)


@api.delete("/programs/<int:record_id>")
@roles_required("admin","coordinator")
def delete_program(record_id):
    with transaction() as conn:
        cursor=conn.cursor(); cursor.execute("SELECT id FROM training_programs WHERE id=%s FOR UPDATE",(record_id,))
        if not cursor.fetchone():return _not_found()
        cursor.execute("UPDATE training_programs SET status='archived' WHERE id=%s",(record_id,))
        cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'archive','training_program',%s)",(g.user["id"],record_id)); cursor.close()
    return jsonify(data={"archived":True,"record_id":record_id})


def _visible_session_query():
    if g.user["role"]=="farmer":
        return _SESSION_SELECT+""" JOIN farmers f ON f.user_id=%s AND f.record_status='active'
                                     JOIN program_farmers pf ON pf.program_id=s.program_id AND pf.farmer_id=f.id
                                    WHERE pf.participation_status<>'withdrawn' AND s.status<>'cancelled'""",(g.user["id"],)
    if g.user["role"]=="trainer":
        return _SESSION_SELECT+" WHERE t.user_id=%s AND s.status<>'cancelled'",(g.user["id"],)
    return _SESSION_SELECT,( )


@api.post("/sessions")
@roles_required("admin","coordinator")
def create_session():
    body,error=_json_body()
    if error:return error
    try:
        program_id=positive_id(body.get("program_id"),"program id"); trainer_id=positive_id(body.get("trainer_id"),"trainer id")
        session_date=_date(body.get("session_date"),"Session date"); start_time=_time(body.get("start_time"),"Start time")
        end_time=_time(body.get("end_time"),"End time") if body.get("end_time") else None
        if end_time and end_time<=start_time:raise ValueError("End time must be after start time.")
        location=required_text(body,"location","Location",200); details=optional_text(body,"session_details",10000)
        status=enum_value(body,"status",("scheduled","completed","cancelled"),"Status","scheduled")
        farmer_ids=body.get("farmer_ids",[])
        if not isinstance(farmer_ids,list) or len(farmer_ids)>500:
            raise ValueError("farmer_ids must be a list of no more than 500 farmers.")
        farmer_ids=[positive_id(value,"farmer id") for value in farmer_ids]
        if len(set(farmer_ids))!=len(farmer_ids):
            raise ValueError("A farmer may only be selected once.")
        with transaction() as conn:
            cursor=conn.cursor()
            cursor.execute("SELECT id FROM training_programs WHERE id=%s AND status='active'",(program_id,))
            if not cursor.fetchone():return api_error("The selected program does not exist or is not active.",400)
            cursor.execute("SELECT id FROM trainers WHERE id=%s AND record_status='active'",(trainer_id,))
            if not cursor.fetchone():return api_error("The selected trainer does not exist or is inactive.",400)
            if farmer_ids:
                placeholders=",".join(["%s"]*len(farmer_ids))
                cursor.execute(f"SELECT id FROM farmers WHERE record_status='active' AND id IN ({placeholders})",tuple(farmer_ids))
                found={row[0] for row in cursor.fetchall()}
                if found!=set(farmer_ids):
                    return api_error("One or more selected farmers are missing or inactive.",400)
            cursor.execute("INSERT INTO training_sessions (program_id,trainer_id,session_date,start_time,end_time,location,session_details,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",(program_id,trainer_id,session_date,start_time,end_time,location,details,status))
            record_id=cursor.lastrowid
            if farmer_ids:
                for farmer_id in farmer_ids:
                    cursor.execute(
                        """INSERT INTO program_farmers (program_id,farmer_id,participation_status)
                           VALUES (%s,%s,'enrolled')
                           ON DUPLICATE KEY UPDATE participation_status=
                             IF(participation_status='withdrawn','enrolled',participation_status)""",
                        (program_id,farmer_id),
                    )
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'create','training_session',%s)",(g.user["id"],record_id));cursor.close()
        return _get(_SESSION_SELECT+" WHERE s.id=%s",record_id)
    except ValueError as exc:return api_error(str(exc),400)


@api.get("/sessions")
@roles_required("admin","coordinator","trainer","farmer","management")
def list_sessions():
    base,base_params=_visible_session_query()
    where,params=_search_filter("training_sessions",("p.program_name","t.full_name","s.location"),{"status","program_id","trainer_id","session_date"})
    if " WHERE " in base and where:base+=" AND "+where[7:]
    else:base+=where
    return _list_response(base+" ORDER BY s.session_date,s.start_time",(*base_params,*params))


@api.get("/sessions/<int:record_id>")
@roles_required("admin","coordinator","trainer","farmer","management")
def get_session(record_id):
    base,params=_visible_session_query()
    query=base+(" AND " if " WHERE " in base else " WHERE ")+"s.id=%s"
    row=fetch_one(query,(*params,record_id))
    return jsonify(data=row) if row else _not_found()


@api.put("/sessions/<int:record_id>")
@roles_required("admin","coordinator","trainer")
def update_session(record_id):
    body,error=_json_body()
    if error:return error
    try:
        current=fetch_one("SELECT s.id,s.program_id,s.trainer_id,s.status,t.user_id AS trainer_user_id FROM training_sessions s JOIN trainers t ON t.id=s.trainer_id WHERE s.id=%s",(record_id,))
        if not current:return _not_found()
        if g.user["role"]=="trainer" and current["trainer_user_id"]!=g.user["id"]:
            return api_error("You may only update your assigned sessions.",403,"permission_denied")
        if g.user["role"]=="trainer" and current["status"]=="cancelled":
            return api_error("A cancelled session must be rescheduled by a coordinator.",409)
        program_id=positive_id(body.get("program_id",current["program_id"]),"program id")
        trainer_id=positive_id(body.get("trainer_id",current["trainer_id"]),"trainer id")
        if g.user["role"]=="trainer" and (program_id!=current["program_id"] or trainer_id!=current["trainer_id"]):
            return api_error("Trainers cannot reassign sessions or change the program.",403,"permission_denied")
        session_date=_date(body.get("session_date"),"Session date"); start_time=_time(body.get("start_time"),"Start time")
        end_time=_time(body.get("end_time"),"End time") if body.get("end_time") else None
        if end_time and end_time<=start_time:raise ValueError("End time must be after start time.")
        location=required_text(body,"location","Location",200)
        details=optional_text(body,"session_details",10000)
        status=enum_value(body,"status",("scheduled","completed","cancelled"),"Status")
        farmer_ids=body.get("farmer_ids",[])
        if not isinstance(farmer_ids,list) or len(farmer_ids)>500:
            raise ValueError("farmer_ids must be a list of no more than 500 farmers.")
        farmer_ids=[positive_id(value,"farmer id") for value in farmer_ids]
        if len(set(farmer_ids))!=len(farmer_ids):
            raise ValueError("A farmer may only be selected once.")
        with transaction() as conn:
            cursor=conn.cursor()
            if farmer_ids and g.user["role"] in {"admin","coordinator"}:
                placeholders=",".join(["%s"]*len(farmer_ids))
                cursor.execute(f"SELECT id FROM farmers WHERE record_status='active' AND id IN ({placeholders})",tuple(farmer_ids))
                found={row[0] for row in cursor.fetchall()}
                if found!=set(farmer_ids):
                    return api_error("One or more selected farmers are missing or inactive.",400)
            cursor.execute("UPDATE training_sessions SET program_id=%s,trainer_id=%s,session_date=%s,start_time=%s,end_time=%s,location=%s,session_details=%s,status=%s WHERE id=%s",(program_id,trainer_id,session_date,start_time,end_time,location,details,status,record_id))
            if farmer_ids and g.user["role"] in {"admin","coordinator"}:
                for farmer_id in farmer_ids:
                    cursor.execute(
                        """INSERT INTO program_farmers (program_id,farmer_id,participation_status)
                           VALUES (%s,%s,'enrolled')
                           ON DUPLICATE KEY UPDATE participation_status=
                             IF(participation_status='withdrawn','enrolled',participation_status)""",
                        (program_id,farmer_id),
                    )
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','training_session',%s)",(g.user["id"],record_id));cursor.close()
        return _get(_SESSION_SELECT+" WHERE s.id=%s",record_id)
    except ValueError as exc:return api_error(str(exc),400)


@api.delete("/sessions/<int:record_id>")
@roles_required("admin","coordinator")
def delete_session(record_id):
    with transaction() as conn:
        cursor=conn.cursor();cursor.execute("SELECT id FROM training_sessions WHERE id=%s FOR UPDATE",(record_id,))
        if not cursor.fetchone():return _not_found()
        cursor.execute("UPDATE training_sessions SET status='cancelled' WHERE id=%s",(record_id,))
        cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'cancel','training_session',%s)",(g.user["id"],record_id));cursor.close()
    return jsonify(data={"cancelled":True,"record_id":record_id})


def _visible_enrollment_query():
    base="""SELECT pf.id,pf.program_id,pf.farmer_id,f.farmer_id AS farmer_code,
                   f.full_name AS farmer_name,p.program_name,CAST(pf.enrollment_date AS CHAR) AS enrollment_date,
                   pf.participation_status,pf.created_at,pf.updated_at
              FROM program_farmers pf JOIN farmers f ON f.id=pf.farmer_id
              JOIN training_programs p ON p.id=pf.program_id"""
    if g.user["role"]=="farmer":return base+" WHERE f.user_id=%s",(g.user["id"],)
    if g.user["role"]=="trainer":return base+""" JOIN training_sessions s ON s.program_id=pf.program_id
                JOIN trainers t ON t.id=s.trainer_id WHERE t.user_id=%s""",(g.user["id"],)
    return base,()


@api.post("/enrollments")
@roles_required("admin","coordinator","farmer")
def create_enrollment():
    body,error=_json_body()
    if error:return error
    try:
        program_id=positive_id(body.get("program_id"),"program id")
        if g.user["role"]=="farmer":
            farmer=fetch_one("SELECT id FROM farmers WHERE user_id=%s",(g.user["id"],))
            if not farmer:return api_error("Your farmer profile is not configured.",409)
            farmer_id=farmer["id"]
        else:
            farmer_id=positive_id(body.get("farmer_id"),"farmer id")
        status=enum_value(body,"participation_status",ENROLLMENT_STATUS,"Participation status","enrolled")
        enrollment_date=_date(body.get("enrollment_date",date.today().isoformat()),"Enrollment date")
        with transaction() as conn:
            cursor=conn.cursor()
            cursor.execute("SELECT id FROM training_programs WHERE id=%s AND status='active'",(program_id,))
            if not cursor.fetchone():return api_error("The selected program does not exist or is not active.",400)
            cursor.execute("SELECT id FROM farmers WHERE id=%s AND record_status='active'",(farmer_id,))
            if not cursor.fetchone():return api_error("The selected farmer does not exist or is inactive.",400)
            cursor.execute("INSERT INTO program_farmers (program_id,farmer_id,enrollment_date,participation_status) VALUES (%s,%s,%s,%s)",(program_id,farmer_id,enrollment_date,status))
            record_id=cursor.lastrowid
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'enroll','program_farmer',%s)",(g.user["id"],record_id));cursor.close()
        return _get("""SELECT pf.id,pf.program_id,pf.farmer_id,f.farmer_id AS farmer_code,
                             f.full_name AS farmer_name,p.program_name,CAST(pf.enrollment_date AS CHAR) AS enrollment_date,
                             pf.participation_status,pf.created_at,pf.updated_at
                        FROM program_farmers pf JOIN farmers f ON f.id=pf.farmer_id
                        JOIN training_programs p ON p.id=pf.program_id WHERE pf.id=%s""",record_id)
    except ValueError as exc:return api_error(str(exc),400)


@api.get("/enrollments")
@roles_required("admin","coordinator","trainer","farmer","management")
def list_enrollments():
    base,base_params=_visible_enrollment_query()
    if " WHERE " in base:
        return _list_response(base+" AND pf.participation_status<>'withdrawn' ORDER BY pf.enrollment_date DESC",base_params)
    return _list_response(base+" WHERE pf.participation_status<>'withdrawn' ORDER BY pf.enrollment_date DESC",base_params)


@api.put("/enrollments/<int:record_id>")
@roles_required("admin","coordinator")
def update_enrollment(record_id):
    body,error=_json_body()
    if error:return error
    try:
        status=enum_value(body,"participation_status",ENROLLMENT_STATUS,"Participation status")
        with transaction() as conn:
            cursor=conn.cursor();cursor.execute("UPDATE program_farmers SET participation_status=%s WHERE id=%s",(status,record_id))
            if cursor.rowcount==0 and not fetch_one("SELECT id FROM program_farmers WHERE id=%s",(record_id,)):return _not_found()
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','program_farmer',%s)",(g.user["id"],record_id));cursor.close()
        return _get("""SELECT pf.id,pf.program_id,pf.farmer_id,f.farmer_id AS farmer_code,
                             f.full_name AS farmer_name,p.program_name,CAST(pf.enrollment_date AS CHAR) AS enrollment_date,
                             pf.participation_status,pf.created_at,pf.updated_at
                        FROM program_farmers pf JOIN farmers f ON f.id=pf.farmer_id
                        JOIN training_programs p ON p.id=pf.program_id WHERE pf.id=%s""",record_id)
    except ValueError as exc:return api_error(str(exc),400)


def _attendance_query():
    query="""SELECT a.id,a.session_id,a.farmer_id,a.attendance_status,a.recorded_by,
                    a.recorded_at,f.farmer_id AS farmer_code,f.full_name AS farmer_name,
                    CAST(s.session_date AS CHAR) AS session_date,s.program_id,p.program_name,t.user_id AS trainer_user_id
               FROM attendance a JOIN farmers f ON f.id=a.farmer_id
               JOIN training_sessions s ON s.id=a.session_id
               JOIN training_programs p ON p.id=s.program_id
               JOIN trainers t ON t.id=s.trainer_id"""
    if g.user["role"]=="farmer":return query+" WHERE f.user_id=%s",(g.user["id"],)
    if g.user["role"]=="trainer":return query+" WHERE t.user_id=%s",(g.user["id"],)
    return query,()


@api.post("/attendance")
@roles_required("admin","coordinator","trainer")
def create_attendance():
    body,error=_json_body()
    if error:return error
    try:
        session_id=positive_id(body.get("session_id"),"session id")
        is_batch=isinstance(body.get("records"),list)
        if is_batch:
            if not body["records"] or len(body["records"])>500:return api_error("Provide between 1 and 500 attendance records.",400)
            records=[]
            for record in body["records"]:
                if not isinstance(record,dict):return api_error("Each attendance record must be a JSON object.",400)
                records.append((positive_id(record.get("farmer_id"),"farmer id"),enum_value(record,"attendance_status",ATTENDANCE_STATUS,"Attendance status")))
            if len({farmer_id for farmer_id,_ in records})!=len(records):
                return api_error("A farmer may only appear once in an attendance submission.",400)
        else:
            records=[(positive_id(body.get("farmer_id"),"farmer id"),enum_value(body,"attendance_status",ATTENDANCE_STATUS,"Attendance status"))]
        with transaction() as conn:
            cursor=conn.cursor()
            cursor.execute("SELECT s.id,s.program_id,t.user_id FROM training_sessions s JOIN trainers t ON t.id=s.trainer_id WHERE s.id=%s AND s.status<>'cancelled'",(session_id,))
            session_row=cursor.fetchone()
            if not session_row:return api_error("The selected training session was not found or was cancelled.",400)
            if g.user["role"]=="trainer" and session_row[2]!=g.user["id"]:
                return api_error("You may only record attendance for your assigned sessions.",403,"permission_denied")
            farmer_ids=[farmer_id for farmer_id,_ in records]
            placeholders=",".join(["%s"]*len(farmer_ids))
            cursor.execute(
                f"""SELECT pf.farmer_id FROM program_farmers pf
                      JOIN farmers f ON f.id=pf.farmer_id
                     WHERE pf.program_id=%s AND pf.participation_status<>'withdrawn'
                       AND f.record_status='active' AND pf.farmer_id IN ({placeholders})""",
                (session_row[1],*farmer_ids),
            )
            enrolled={row[0] for row in cursor.fetchall()}
            if enrolled!=set(farmer_ids):
                return api_error("Every farmer must be active and enrolled in the session's training program.",400)
            record_ids=[]
            for farmer_id,status in records:
                cursor.execute(
                    """INSERT INTO attendance (session_id,farmer_id,attendance_status,recorded_by)
                       VALUES (%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE attendance_status=VALUES(attendance_status),
                                               recorded_by=VALUES(recorded_by),recorded_at=CURRENT_TIMESTAMP""",
                    (session_id,farmer_id,status,g.user["id"]),
                )
                cursor.execute("SELECT id FROM attendance WHERE session_id=%s AND farmer_id=%s",(session_id,farmer_id))
                record_id=cursor.fetchone()[0]
                record_ids.append(record_id)
                cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'record','attendance',%s)",(g.user["id"],record_id))
            cursor.close()
        if is_batch:
            return jsonify(data={"saved_count":len(record_ids),"ids":record_ids}),201
        base,params=_attendance_query()
        return _get(base+(" AND " if " WHERE " in base else " WHERE ")+"a.id=%s",record_ids[0],params)
    except ValueError as exc:return api_error(str(exc),400)


@api.get("/attendance")
@roles_required("admin","coordinator","trainer","farmer","management")
def list_attendance():
    base,base_params=_attendance_query()
    where,params=_search_filter("attendance",("f.full_name","p.program_name"),{"attendance_status","session_id","farmer_id"})
    if " WHERE " in base and where:base+=" AND "+where[7:]
    else:base+=where
    return _list_response(base+" ORDER BY a.recorded_at DESC",(*base_params,*params))


@api.put("/attendance/<int:record_id>")
@roles_required("admin","coordinator","trainer")
def update_attendance(record_id):
    body,error=_json_body()
    if error:return error
    try:
        status=enum_value(body,"attendance_status",ATTENDANCE_STATUS,"Attendance status")
        visible,params=_attendance_query()
        current=fetch_one(visible+(" AND " if " WHERE " in visible else " WHERE ")+"a.id=%s",(*params,record_id))
        if not current:return _not_found()
        if g.user["role"]=="trainer" and current["trainer_user_id"]!=g.user["id"]:
            return api_error("You may only update attendance for your assigned sessions.",403,"permission_denied")
        with transaction() as conn:
            cursor=conn.cursor();cursor.execute("UPDATE attendance SET attendance_status=%s,recorded_by=%s WHERE id=%s",(status,g.user["id"],record_id))
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'update','attendance',%s)",(g.user["id"],record_id));cursor.close()
        base,params=_attendance_query()
        return _get(base+(" AND " if " WHERE " in base else " WHERE ")+"a.id=%s",record_id,params)
    except ValueError as exc:return api_error(str(exc),400)


def _progress_query():
    query="""SELECT DISTINCT tp.id,tp.farmer_id,tp.program_id,tp.progress_details,tp.progress_percent,
                    tp.completion_status,tp.result,tp.updated_by,tp.updated_at,
                    f.farmer_id AS farmer_code,f.full_name AS farmer_name,
                    p.program_name,t.user_id AS trainer_user_id
               FROM training_progress tp JOIN farmers f ON f.id=tp.farmer_id
               JOIN training_programs p ON p.id=tp.program_id
               LEFT JOIN training_sessions s ON s.program_id=tp.program_id
               LEFT JOIN trainers t ON t.id=s.trainer_id"""
    if g.user["role"]=="farmer":return query+" WHERE f.user_id=%s",(g.user["id"],)
    if g.user["role"]=="trainer":return query+" WHERE t.user_id=%s",(g.user["id"],)
    return query,()


def _save_progress(body, record_id=None):
    farmer_id=positive_id(body.get("farmer_id"),"farmer id")
    program_id=positive_id(body.get("program_id"),"program id")
    details=optional_text(body,"progress_details",10000)
    status=enum_value(body,"completion_status",COMPLETION_STATUS,"Completion status")
    percent=body.get("progress_percent", 100 if status=="completed" else 0 if status=="not_started" else 1)
    if isinstance(percent,bool) or not isinstance(percent,int) or percent<0 or percent>100:
        raise ValueError("Progress percentage must be an integer between 0 and 100.")
    if (status=="completed" and percent!=100) or (status=="not_started" and percent!=0):
        raise ValueError("Progress percentage must match the completion status.")
    result=optional_text(body,"result",255)
    if g.user["role"]=="trainer":
        _,error=_trainer_can_manage_program(program_id)
        if error:return None,error
    with transaction() as conn:
        cursor=conn.cursor()
        cursor.execute("SELECT id FROM farmers WHERE id=%s AND record_status='active'",(farmer_id,))
        if not cursor.fetchone():return None,api_error("The selected farmer does not exist or is inactive.",400)
        cursor.execute("SELECT id FROM training_programs WHERE id=%s",(program_id,))
        if not cursor.fetchone():return None,api_error("The selected training program was not found.",400)
        cursor.execute("SELECT id FROM program_farmers WHERE program_id=%s AND farmer_id=%s AND participation_status<>'withdrawn'",(program_id,farmer_id))
        if not cursor.fetchone():return None,api_error("The farmer must be enrolled in this training program before progress is recorded.",400)
        if record_id:
            cursor.execute("SELECT id,farmer_id,program_id FROM training_progress WHERE id=%s FOR UPDATE",(record_id,))
            prior=cursor.fetchone()
            if not prior:return None,_not_found()
            if prior[1]!=farmer_id or prior[2]!=program_id:return None,api_error("A progress record cannot be reassigned to another farmer or program.",400)
            cursor.execute("UPDATE training_progress SET progress_details=%s,progress_percent=%s,completion_status=%s,result=%s,updated_by=%s WHERE id=%s",(details,percent,status,result,g.user["id"],record_id))
            saved_id=record_id
            action="update"
        else:
            cursor.execute("INSERT INTO training_progress (farmer_id,program_id,progress_details,progress_percent,completion_status,result,updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",(farmer_id,program_id,details,percent,status,result,g.user["id"]))
            saved_id=cursor.lastrowid
            action="create"
        cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,%s,'training_progress',%s)",(g.user["id"],action,saved_id))
        cursor.close()
    return saved_id,None


def _trainer_can_manage_program(program_id):
    assigned=fetch_one("""SELECT s.id FROM training_sessions s JOIN trainers t ON t.id=s.trainer_id
                           WHERE t.user_id=%s AND s.program_id=%s AND s.status<>'cancelled' LIMIT 1""",(g.user["id"],program_id))
    if not assigned:return None,api_error("You are not assigned to a session for this program.",403,"permission_denied")
    return assigned,None


@api.post("/progress")
@roles_required("admin","coordinator","trainer")
def create_progress():
    body,error=_json_body()
    if error:return error
    try:
        record_id,record_error=_save_progress(body)
        if record_error:return record_error
        base,params=_progress_query()
        return _get(base+(" AND " if " WHERE " in base else " WHERE ")+"tp.id=%s",record_id,params)
    except ValueError as exc:return api_error(str(exc),400)


@api.get("/progress")
@roles_required("admin","coordinator","trainer","farmer","management")
def list_progress():
    base,base_params=_progress_query()
    where,params=_search_filter("training_progress",("f.full_name","p.program_name"),{"completion_status","program_id","farmer_id"})
    if " WHERE " in base and where:base+=" AND "+where[7:]
    else:base+=where
    return _list_response(base+" ORDER BY tp.updated_at DESC",(*base_params,*params))


@api.get("/progress/<int:record_id>")
@roles_required("admin","coordinator","trainer","farmer","management")
def get_progress(record_id):
    base,params=_progress_query()
    return _get(base+(" AND " if " WHERE " in base else " WHERE ")+"tp.id=%s",record_id,params)


@api.put("/progress/<int:record_id>")
@roles_required("admin","coordinator","trainer")
def update_progress(record_id):
    body,error=_json_body()
    if error:return error
    try:
        saved_id,record_error=_save_progress(body,record_id)
        if record_error:return record_error
        base,params=_progress_query()
        return _get(base+(" AND " if " WHERE " in base else " WHERE ")+"tp.id=%s",saved_id,params)
    except ValueError as exc:return api_error(str(exc),400)
