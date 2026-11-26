from flask import g, jsonify

from ..database import fetch_all, fetch_one
from ..routes import api
from ..security import roles_required


def _count(query, params=()):
    return fetch_one(query, params)["total"]


def _global_dashboard():
    return {
        "farmers": _count("SELECT COUNT(*) AS total FROM farmers WHERE record_status='active'"),
        "trainers": _count("SELECT COUNT(*) AS total FROM trainers WHERE record_status='active'"),
        "programs": _count("SELECT COUNT(*) AS total FROM training_programs WHERE status='active'"),
        "upcoming_sessions": _count("SELECT COUNT(*) AS total FROM training_sessions WHERE status='scheduled' AND session_date>=CURRENT_DATE"),
        "attendance_records": _count("SELECT COUNT(*) AS total FROM attendance"),
        "present_records": _count("SELECT COUNT(*) AS total FROM attendance WHERE attendance_status='present'"),
        "completed_progress": _count("SELECT COUNT(*) AS total FROM training_progress WHERE completion_status='completed'"),
    }


@api.get("/dashboard/admin")
@roles_required("admin")
def admin_dashboard():
    stats = _global_dashboard()
    stats["users"] = _count("SELECT COUNT(*) AS total FROM users")
    stats["inactive_users"] = _count("SELECT COUNT(*) AS total FROM users WHERE account_status='inactive'")
    return jsonify(data=stats)


@api.get("/dashboard/coordinator")
@roles_required("admin","coordinator")
def coordinator_dashboard():
    return jsonify(data=_global_dashboard())


@api.get("/dashboard/management")
@roles_required("admin","management")
def management_dashboard():
    return jsonify(data=_global_dashboard())


@api.get("/dashboard/trainer")
@roles_required("admin","trainer")
def trainer_dashboard():
    trainer=fetch_one("SELECT id FROM trainers WHERE user_id=%s AND record_status='active'",(g.user["id"],))
    if not trainer:
        return jsonify(data={"assigned_programs":0,"assigned_sessions":0,"farmers_invited":0,"attendance_records":0,"upcoming_sessions":[]})
    trainer_id=trainer["id"]
    stats={
        "assigned_programs":_count("SELECT COUNT(DISTINCT program_id) AS total FROM training_sessions WHERE trainer_id=%s AND status<>'cancelled'",(trainer_id,)),
        "assigned_sessions":_count("SELECT COUNT(*) AS total FROM training_sessions WHERE trainer_id=%s AND status<>'cancelled'",(trainer_id,)),
        "farmers_invited":_count("""SELECT COUNT(DISTINCT pf.farmer_id) AS total FROM program_farmers pf
                                      JOIN training_sessions s ON s.program_id=pf.program_id
                                     WHERE s.trainer_id=%s AND s.status<>'cancelled'""",(trainer_id,)),
        "attendance_records":_count("""SELECT COUNT(*) AS total FROM attendance a
                                        JOIN training_sessions s ON s.id=a.session_id
                                       WHERE s.trainer_id=%s""",(trainer_id,)),
        "upcoming_sessions":fetch_all("""SELECT s.id,CAST(s.session_date AS CHAR) AS session_date,
                                                  CAST(s.start_time AS CHAR) AS start_time,
                                                  s.location,p.program_name
                                           FROM training_sessions s JOIN training_programs p ON p.id=s.program_id
                                          WHERE s.trainer_id=%s AND s.status='scheduled'
                                            AND s.session_date>=CURRENT_DATE
                                          ORDER BY s.session_date,s.start_time LIMIT 10""",(trainer_id,)),
    }
    return jsonify(data=stats)


@api.get("/dashboard/farmer")
@roles_required("admin","farmer")
def farmer_dashboard():
    farmer=fetch_one("SELECT id,farmer_id,full_name,village,phone,email FROM farmers WHERE user_id=%s",(g.user["id"],))
    if not farmer:
        return jsonify(error={"code":"farmer_profile_missing","message":"Your farmer profile has not been configured."}),409
    farmer_id=farmer["id"]
    stats={
        "profile":farmer,
        "available_programs":_count("SELECT COUNT(*) AS total FROM training_programs WHERE status='active'"),
        "enrolled_programs":_count("SELECT COUNT(*) AS total FROM program_farmers WHERE farmer_id=%s AND participation_status<>'withdrawn'",(farmer_id,)),
        "attendance_records":_count("SELECT COUNT(*) AS total FROM attendance WHERE farmer_id=%s",(farmer_id,)),
        "upcoming_sessions":fetch_all("""SELECT s.id,CAST(s.session_date AS CHAR) AS session_date,
                                                  CAST(s.start_time AS CHAR) AS start_time,
                                                  s.location,p.program_name,t.full_name AS trainer_name
                                           FROM program_farmers pf JOIN training_sessions s ON s.program_id=pf.program_id
                                           JOIN training_programs p ON p.id=s.program_id
                                           JOIN trainers t ON t.id=s.trainer_id
                                          WHERE pf.farmer_id=%s AND pf.participation_status<>'withdrawn'
                                            AND s.status='scheduled' AND s.session_date>=CURRENT_DATE
                                          ORDER BY s.session_date,s.start_time LIMIT 10""",(farmer_id,)),
        "attendance":fetch_all("""SELECT a.id,a.attendance_status,CAST(s.session_date AS CHAR) AS session_date,p.program_name
                                    FROM attendance a JOIN training_sessions s ON s.id=a.session_id
                                    JOIN training_programs p ON p.id=s.program_id
                                   WHERE a.farmer_id=%s ORDER BY s.session_date DESC LIMIT 20""",(farmer_id,)),
        "progress":fetch_all("""SELECT tp.id,p.program_name,tp.completion_status,tp.result,tp.progress_details,tp.updated_at
                                  FROM training_progress tp JOIN training_programs p ON p.id=tp.program_id
                                 WHERE tp.farmer_id=%s ORDER BY tp.updated_at DESC""",(farmer_id,)),
    }
    return jsonify(data=stats)
