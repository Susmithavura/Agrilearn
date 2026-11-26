from datetime import date

from flask import jsonify, request

from ..database import fetch_all
from ..routes import api
from ..security import api_error, roles_required
from .resources import _list_response, _page_params

REPORT_ACCESS = ("admin", "coordinator", "management")


def _date_filter(column):
    clauses = []
    params = []
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if start:
        try:
            date.fromisoformat(start)
        except ValueError:
            return None, None, api_error("start_date must use YYYY-MM-DD format.", 400)
        clauses.append(f"{column} >= %s")
        params.append(start)
    if end:
        try:
            date.fromisoformat(end)
        except ValueError:
            return None, None, api_error("end_date must use YYYY-MM-DD format.", 400)
        clauses.append(f"{column} < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(end)
    if start and end and start > end:
        return None, None, api_error("start_date must be on or before end_date.", 400)
    program_id = request.args.get("program_id")
    if program_id:
        try:
            program_id = int(program_id)
            if program_id < 1:
                raise ValueError
        except ValueError:
            return None, None, api_error("program_id must be a positive integer.", 400)
    return clauses, params, program_id


def _report(query, base_params=(), date_column=None, status_column=None):
    clauses, params, program_id = [], [], None
    if date_column:
        clauses, params, program_id = _date_filter(date_column)
        if clauses is None:
            return program_id
    if program_id:
        return api_error("program_id is not supported for this report.", 400)
    status = request.args.get("status")
    if status and status_column:
        allowed_status = ("active", "inactive") if status_column in {"f.record_status", "t.record_status"} else ()
        if allowed_status and status not in allowed_status:
            return api_error(f"status must be one of: {', '.join(allowed_status)}.", 400)
        clauses.append(f"{status_column} = %s")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    page, per_page, offset = _page_params()
    rows = fetch_all(query + " ORDER BY 1 LIMIT %s OFFSET %s", (*base_params, *params, per_page, offset))
    return jsonify(data=rows, meta={"page": page, "per_page": per_page, "count": len(rows)})


@api.get("/reports/farmers")
@roles_required(*REPORT_ACCESS)
def report_farmers():
    return _report(
        """SELECT f.farmer_id,f.full_name,f.village,f.phone,f.email,f.record_status,
                  f.created_at,f.updated_at FROM farmers f""",
        date_column="f.created_at", status_column="f.record_status",
    )


@api.get("/reports/trainers")
@roles_required(*REPORT_ACCESS)
def report_trainers():
    return _report(
        """SELECT t.trainer_id,t.full_name,t.specialization,t.phone,t.email,t.record_status,
                  t.created_at,t.updated_at FROM trainers t""",
        date_column="t.created_at", status_column="t.record_status",
    )


@api.get("/reports/programs")
@roles_required(*REPORT_ACCESS)
def report_programs():
    clauses, params, program_id = _date_filter("p.created_at")
    if clauses is None:
        return program_id
    if program_id:
        return api_error("program_id is not supported for this report.", 400)
    status = request.args.get("status")
    if status:
        if status not in {"active", "draft", "archived"}:
            return api_error("status must be active, draft or archived.", 400)
        clauses.append("p.status=%s")
        params.append(status)
    query = """SELECT p.id,p.program_name,p.category,p.level,p.duration,p.status,p.created_at,
                      COUNT(DISTINCT pf.farmer_id) AS enrolled_farmers,
                      COUNT(DISTINCT s.id) AS scheduled_sessions
                 FROM training_programs p
                 LEFT JOIN program_farmers pf ON pf.program_id=p.id
                 LEFT JOIN training_sessions s ON s.program_id=p.id"""
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " GROUP BY p.id,p.program_name,p.category,p.level,p.duration,p.status,p.created_at"
    page, per_page, offset = _page_params()
    rows = fetch_all(query + " ORDER BY p.id LIMIT %s OFFSET %s", (*params, per_page, offset))
    return jsonify(data=rows, meta={"page": page, "per_page": per_page, "count": len(rows)})


@api.get("/reports/schedules")
@roles_required(*REPORT_ACCESS)
def report_schedules():
    return report_sessions_query()


@api.get("/reports/sessions")
@roles_required(*REPORT_ACCESS)
def report_sessions():
    return report_sessions_query()


def report_sessions_query():
    clauses, params, program_id = _date_filter("s.session_date")
    if clauses is None:
        return program_id
    trainer_id = request.args.get("trainer_id")
    if trainer_id:
        try:
            trainer_id = int(trainer_id)
            if trainer_id < 1:
                raise ValueError
        except ValueError:
            return api_error("trainer_id must be a positive integer.", 400)
        clauses.append("s.trainer_id=%s")
        params.append(trainer_id)
    if program_id:
        clauses.append("s.program_id=%s")
        params.append(program_id)
    status = request.args.get("status")
    if status:
        if status not in {"scheduled", "completed", "cancelled"}:
            return api_error("status must be scheduled, completed or cancelled.", 400)
        clauses.append("s.status=%s")
        params.append(status)
    query = """SELECT s.id,CAST(s.session_date AS CHAR) AS session_date,
                      CAST(s.start_time AS CHAR) AS start_time,
                      CAST(s.end_time AS CHAR) AS end_time,s.location,s.status,
                      p.program_name,t.trainer_id,t.full_name AS trainer_name
                 FROM training_sessions s JOIN training_programs p ON p.id=s.program_id
                 JOIN trainers t ON t.id=s.trainer_id"""
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    page, per_page, offset = _page_params()
    rows = fetch_all(query + " ORDER BY s.session_date,s.start_time LIMIT %s OFFSET %s", (*params,per_page,offset))
    return jsonify(data=rows,meta={"page":page,"per_page":per_page,"count":len(rows)})


@api.get("/reports/attendance")
@roles_required(*REPORT_ACCESS)
def report_attendance():
    clauses, params, program_id = _date_filter("s.session_date")
    if clauses is None:
        return program_id
    if program_id:
        clauses.append("s.program_id=%s")
        params.append(program_id)
    status=request.args.get("status")
    if status:
        if status not in {"present","absent"}:
            return api_error("status must be present or absent.",400)
        clauses.append("a.attendance_status=%s")
        params.append(status)
    query="""SELECT a.id,f.farmer_id,f.full_name AS farmer_name,p.program_name,
                    CAST(s.session_date AS CHAR) AS session_date,s.location,a.attendance_status,a.recorded_at,
                    u.full_name AS recorded_by
               FROM attendance a JOIN farmers f ON f.id=a.farmer_id
               JOIN training_sessions s ON s.id=a.session_id
               JOIN training_programs p ON p.id=s.program_id
               JOIN users u ON u.id=a.recorded_by"""
    if clauses:query+=" WHERE "+" AND ".join(clauses)
    page,per_page,offset=_page_params()
    rows=fetch_all(query+" ORDER BY s.session_date DESC LIMIT %s OFFSET %s",(*params,per_page,offset))
    return jsonify(data=rows,meta={"page":page,"per_page":per_page,"count":len(rows)})


@api.get("/reports/progress")
@roles_required(*REPORT_ACCESS)
def report_progress():
    clauses,params,program_id=_date_filter("tp.updated_at")
    if clauses is None:return program_id
    if program_id:
        clauses.append("tp.program_id=%s");params.append(program_id)
    status=request.args.get("status")
    if status:
        if status not in {"not_started","in_progress","completed"}:return api_error("Invalid completion status.",400)
        clauses.append("tp.completion_status=%s");params.append(status)
    query="""SELECT f.farmer_id,f.full_name AS farmer_name,p.program_name,
                    tp.progress_details,tp.progress_percent,tp.completion_status,tp.result,tp.updated_at
               FROM training_progress tp JOIN farmers f ON f.id=tp.farmer_id
               JOIN training_programs p ON p.id=tp.program_id"""
    if clauses:query+=" WHERE "+" AND ".join(clauses)
    page,per_page,offset=_page_params()
    rows=fetch_all(query+" ORDER BY tp.updated_at DESC LIMIT %s OFFSET %s",(*params,per_page,offset))
    return jsonify(data=rows,meta={"page":page,"per_page":per_page,"count":len(rows)})
