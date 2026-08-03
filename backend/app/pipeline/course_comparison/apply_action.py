

def apply_action(
    action: str,
    detail: dict,
    sn: str,
    professor: str,
    parsed_new: dict | None,
    to_create: list,
    to_delete: list,
    to_activate: list,
    to_hide: list,
    to_update: list,
    alerts: list,
    logs: list,
):
    phase = "2"
    if action == "create":
        to_create.append({"shortname": sn, "professor": professor, **detail})
        logs.append({
            "phase": phase, "action": "course_created",
            "identifier": sn, "detail": detail,
        })
    elif action == "create_with_template":
        to_create.append({
            "shortname": sn,
            "professor": professor,
            "template_shortname": detail.get("template_shortname"),
            **detail,
        })
        logs.append({
            "phase": phase, "action": "course_created_with_template",
            "identifier": sn, "detail": detail,
        })
    elif action == "recreate":
        old_sn = detail.get("old_shortname", sn)
        to_delete.append({"shortname": old_sn, **detail})
        to_create.append({
            "shortname": sn,
            "professor": professor,
            "recreate": True,
            **detail,
        })
        logs.append({
            "phase": phase, "action": "course_recreated",
            "identifier": sn, "detail": detail,
        })
    elif action == "hide_and_create":
        old_sn = detail.get("old_shortname", sn)
        to_hide.append({"shortname": old_sn, **detail})
        to_create.append({"shortname": sn, "professor": professor, **detail})
        alerts.append({
            "shortname": sn,
            "reason": "teacher_change_recent",
            "old_professor": detail.get("old_professor", ""),
            "new_professor": detail.get("new_professor", ""),
            "age_seconds": detail.get("age_seconds", 0),
        })
        logs.append({
            "phase": phase, "action": "course_hidden_and_created",
            "identifier": sn, "detail": detail,
        })
    elif action == "rename_group":
        entry = {
            "old_shortname": detail["old_shortname"],
            "shortname": sn,
            "professor": professor,
            "reason": detail.get("reason", ""),
        }
        if detail.get("reactivate"):
            entry["reactivate"] = True
            to_activate.append({"shortname": detail["old_shortname"], **detail})
        to_update.append(entry)
        logs.append({
            "phase": phase, "action": "course_renamed",
            "identifier": sn,
            "detail": {**detail, "new_shortname": sn},
        })
    elif action == "activate":
        to_activate.append({"shortname": sn, **detail})
        logs.append({
            "phase": phase, "action": "course_activated",
            "identifier": sn, "detail": detail,
        })
    elif action == "create_with_alert":
        to_create.append({"shortname": sn, "professor": professor, **detail})
        alerts.append({
            "shortname": sn,
            "reason": detail["reason"],
            "old_professor": detail.get("old_professor", ""),
            "new_professor": detail.get("new_professor", ""),
            "age_seconds": detail.get("age_seconds", 0),
        })
        logs.append({
            "phase": phase, "action": "alert_teacher_change_recent",
            "identifier": sn, "detail": detail,
        })
    elif action == "alert_orphan":
        alerts.append({
            "shortname": sn,
            "reason": "orphan_course",
            "old_professor": detail.get("old_professor", ""),
            "new_professor": detail.get("professor", ""),
        })
        logs.append({
            "phase": phase, "action": "alert_orphan_course",
            "identifier": sn, "detail": detail,
        })
    elif action == "none":
        logs.append({
            "phase": phase, "action": "course_unchanged",
            "identifier": sn, "detail": detail,
        })
