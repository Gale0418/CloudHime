from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HELPER_AVATAR_LIMIT = 16
VISIBLE_TASK_LIMIT = 10
VISIBLE_AGENT_LIMIT = 15
VALID_STATUSES = {"Intake", "In Progress", "Blocked", "Review", "Waiting", "Done"}
TASK_TYPES_TO_SHOW = {"task", "subtask"}
RNG = random.SystemRandom()

STATUS_ZONE_MAP = {
    "Intake": "Intake",
    "Ready": "Intake",
    "In Progress": "In Progress",
    "Blocked": "Blocked",
    "Review": "Review",
    "Waiting": "Done",
    "Done": "Done",
}

STATUS_AVATAR_OVERRIDES = {
    "Blocked": 6,
    "Waiting": 2,
}

TASK_STATUS_ALIASES = {
    "backlog": "Intake",
    "ready": "Intake",
    "intake": "Intake",
    "doing": "In Progress",
    "progress": "In Progress",
    "in progress": "In Progress",
    "blocked": "Blocked",
    "review": "Review",
    "waiting": "Done",
    "done": "Done",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def safe_text(path: Path) -> str:
    try:
        return read_text(path)
    except Exception:
        return ""


def split_value(line: str) -> str:
    if ":" in line:
        return line.split(":", 1)[1].strip()
    if "：" in line:
        return line.split("：", 1)[1].strip()
    return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_status(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Intake"
    if raw in VALID_STATUSES:
        return raw
    lowered = raw.lower()
    aliases = {
        "ready": "Intake",
        "backlog": "Intake",
        "todo": "Intake",
        "doing": "In Progress",
        "working": "In Progress",
        "progress": "In Progress",
        "reviewing": "Review",
        "checking": "Review",
        "waiting": "Waiting",
        "blocked": "Blocked",
        "done": "Done",
        "complete": "Done",
        "completed": "Done",
    }
    return aliases.get(lowered, "Intake")


def normalize_task_status(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Intake"
    if raw in VALID_STATUSES:
        return raw
    return TASK_STATUS_ALIASES.get(raw.lower(), normalize_status(raw))


def visual_zone_for_status(status: str) -> str:
    return STATUS_ZONE_MAP.get(status, "In Progress")


def avatar_for_status(status: str, avatar: int) -> int:
    return STATUS_AVATAR_OVERRIDES.get(status, avatar)


def sample_avatar(used_avatars: set[int]) -> int:
    available = [avatar for avatar in range(1, HELPER_AVATAR_LIMIT + 1) if avatar not in used_avatars]
    avatar = RNG.choice(available) if available else RNG.randint(1, HELPER_AVATAR_LIMIT)
    used_avatars.add(avatar)
    return avatar


def extract_goal(project_text: str) -> str:
    fallback = "CloudHime demo readiness"
    for line in project_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- Goal:", "Goal:", "- 目標:", "目標:", "- 目標：", "目標：")):
            value = split_value(stripped)
            return value or fallback
    return fallback


def extract_progress(progress_text: str) -> int:
    match = re.search(r"(\d{1,3})%", progress_text)
    if match:
        return max(0, min(100, int(match.group(1))))
    return 0


def split_list_value(value: str) -> list[str]:
    pieces = re.split(r"[、,，/|｜;；]", value)
    return [piece.strip() for piece in pieces if piece.strip()]


def parse_markdown_table(tasks_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in tasks_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("| CH-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        rows.append(
            {
                "id": cells[0],
                "title": cells[1],
                "type": cells[2] if len(cells) > 2 else "",
                "parent": cells[3] if len(cells) > 3 else "",
                "priority": cells[4] if len(cells) > 4 else "",
                "status": normalize_task_status(cells[5] if len(cells) > 5 else ""),
                "owner": cells[6] if len(cells) > 6 else "",
                "blocked_by": cells[7] if len(cells) > 7 else "",
                "next_action": cells[8] if len(cells) > 8 else "",
                "verification": cells[9] if len(cells) > 9 else "",
                "estimate": cells[10] if len(cells) > 10 else "",
                "labels": cells[11] if len(cells) > 11 else "",
                "comments": cells[12] if len(cells) > 12 else "",
            }
        )
    return rows


def should_show_task(task: dict[str, Any]) -> bool:
    return str(task.get("type") or "").strip().lower() in TASK_TYPES_TO_SHOW


def task_title(task: dict[str, Any]) -> str:
    return str(task.get("title") or task.get("id") or "任務")


def task_note(task: dict[str, Any]) -> str:
    next_action = str(task.get("next_action") or "").strip()
    verification = str(task.get("verification") or "").strip()
    if next_action and verification:
        return f"{next_action} ｜ {verification}"
    return next_action or verification or task_title(task)


def task_display_status(task: dict[str, Any]) -> str:
    status = str(task.get("status") or "Intake")
    return status if status in VALID_STATUSES else normalize_task_status(status)


def load_previous_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        data = json.loads(read_text(state_path))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_task_state(project_text: str, tasks_text: str, previous_state: dict[str, Any]) -> dict[str, Any]:
    goal = extract_goal(project_text)
    work_items = [task for task in parse_markdown_table(tasks_text) if should_show_task(task)]
    if not work_items:
        return {}

    previous_completed = previous_state.get("completedAtByTaskId")
    if not isinstance(previous_completed, dict):
        previous_completed = {}

    used_avatars: set[int] = set()
    non_done_tasks: list[dict[str, Any]] = []
    done_candidates: list[dict[str, Any]] = []
    done_history: dict[str, str] = {}

    for task in work_items:
        status = task_display_status(task)
        if status == "Done":
            completed_at = previous_completed.get(task["id"])
            if not isinstance(completed_at, str) or not completed_at.strip():
                completed_at = now_iso()
            done_history[task["id"]] = completed_at.strip()
            done_candidates.append(
                {
                    "id": task["id"],
                    "name": task_title(task),
                    "task": task_note(task),
                    "status": "Done",
                    "zone": "Done",
                    "avatar": avatar_for_status("Done", sample_avatar(used_avatars)),
                    "active": True,
                    "completedAt": completed_at.strip(),
                }
            )
            continue
        non_done_tasks.append(
            {
                "id": task["id"],
                "name": task_title(task),
                "task": task_note(task),
                "status": status,
                "zone": visual_zone_for_status(status),
                "avatar": avatar_for_status(status, sample_avatar(used_avatars)),
                "active": True,
            }
        )

    visible_non_done = non_done_tasks[:VISIBLE_TASK_LIMIT]
    hidden_non_done_count = max(0, len(non_done_tasks) - len(visible_non_done))

    done_candidates.sort(key=lambda item: item.get("completedAt") or "")
    visible_done_capacity = max(0, VISIBLE_AGENT_LIMIT - len(visible_non_done))
    visible_done = done_candidates[:visible_done_capacity]
    hidden_done_count = max(0, len(done_candidates) - len(visible_done))

    agents = visible_non_done + visible_done
    if not agents:
        agents = [
            {
                "id": "task-fallback",
                "name": goal,
                "task": goal,
                "status": "Intake",
                "zone": visual_zone_for_status("Intake"),
                "avatar": avatar_for_status("Intake", sample_avatar(used_avatars)),
                "active": True,
            }
        ]

    status_order = ["In Progress", "Blocked", "Review", "Intake"]
    status = next(
        (candidate for candidate in status_order if any(agent["status"] == candidate for agent in visible_non_done)),
        "Done",
    )

    done_count = len(done_candidates)
    progress = round((done_count / len(work_items)) * 100) if work_items else 0
    active_items = [agent["name"] for agent in visible_non_done] or [goal]
    blocked_items = [f"{agent['name']}：{agent['task']}" for agent in visible_non_done if agent["status"] == "Blocked"]
    review_items = [f"{agent['name']}：{agent['task']}" for agent in visible_non_done if agent["status"] == "Review"]

    current_ids = {task["id"] for task in work_items}
    completed_history = {
        task_id: completed_at
        for task_id, completed_at in previous_completed.items()
        if task_id in current_ids
    }
    completed_history.update(done_history)
    for task in work_items:
        if task_display_status(task) != "Done":
            completed_history.pop(task["id"], None)

    return {
        "status": status,
        "goal": goal,
        "progress": progress,
        "active": active_items,
        "blocked": blocked_items,
        "review": review_items,
        "agents": agents,
        "completedAtByTaskId": completed_history,
        "visibleTaskCount": len(visible_non_done),
        "restTaskCount": len(visible_done),
        "hiddenTaskCount": hidden_non_done_count + hidden_done_count,
        "doneTaskCount": done_count,
        "totalTaskCount": len(work_items),
        "visibleAgentCount": len(agents),
    }


def read_roster(root: Path) -> list[dict[str, Any]]:
    roster_path = root / "active-agents.json"
    if not roster_path.exists():
        return []
    try:
        data = json.loads(read_text(roster_path))
    except Exception:
        return []

    agents = data.get("agents") if isinstance(data, dict) else data
    if not isinstance(agents, list):
        return []
    return [agent for agent in agents if isinstance(agent, dict)]


def is_active_agent(raw_agent: dict[str, Any]) -> bool:
    value = raw_agent.get("active")
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "inactive"}
    return bool(value)


def extract_status(progress_text: str, roster_count: int) -> str:
    for line in progress_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- Current status:", "Current status:", "- 目前狀態:", "目前狀態:")):
            value = split_value(stripped)
            value = re.split(r"[|｜]", value, maxsplit=1)[0].strip()
            return normalize_status(value)
    return "In Progress" if roster_count > 1 else "Intake"


def extract_blocked(progress_text: str, roster: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    capture = False
    for raw_line in progress_text.splitlines():
        line = raw_line.strip()
        if line.startswith(("## Blocked", "## 阻塞", "## 卡住", "- Blocked:", "- 阻塞:", "- 卡住:")):
            capture = True
            value = split_value(line)
            if value:
                items.extend(split_list_value(value))
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.startswith("- "):
            value = line[2:].strip()
            if value:
                items.append(value)

    if items:
        return items

    items = [
        f"{agent.get('name', '子AGENT')}：{agent.get('task', '')}"
        for agent in roster
        if agent.get("id") != "agent-main"
        and normalize_status(str(agent.get("status") or "")) == "Blocked"
        and is_active_agent(agent)
    ]
    return items


def extract_active_items(roster: list[dict[str, Any]], goal: str) -> list[str]:
    items = [
        str(agent.get("task") or agent.get("name") or goal)
        for agent in roster
        if agent.get("id") != "agent-main"
        and is_active_agent(agent)
        and normalize_status(str(agent.get("status") or "")) != "Done"
    ]
    return items or [goal]


def active_agent_entries(roster: list[dict[str, Any]], goal: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    used_avatars: set[int] = set()

    for index, raw_agent in enumerate(roster, start=1):
        if raw_agent.get("id") == "agent-main":
            continue
        if not is_active_agent(raw_agent):
            continue
        status = normalize_status(str(raw_agent.get("status") or "In Progress"))
        if status == "Done":
            continue
        explicit_avatar = raw_agent.get("avatar")
        if explicit_avatar is None:
            avatar = sample_avatar(used_avatars)
        else:
            try:
                avatar = max(1, min(HELPER_AVATAR_LIMIT, int(explicit_avatar)))
            except Exception:
                avatar = sample_avatar(used_avatars)
            used_avatars.add(avatar)

        name = str(raw_agent.get("name") or f"子AGENT {index}")
        task = str(raw_agent.get("task") or goal)
        entries.append(
            {
                "id": str(raw_agent.get("id") or f"agent-{index}"),
                "name": name,
                "task": task,
                "status": status,
                "zone": visual_zone_for_status(status),
                "avatar": avatar_for_status(status, avatar),
                "active": True,
            }
        )
    return entries


def legacy_task_state(project_text: str, progress_text: str, roster: list[dict[str, Any]]) -> dict[str, Any]:
    goal = extract_goal(project_text)
    roster_status = extract_status(progress_text, len(roster))
    progress = extract_progress(progress_text)
    active_entries = active_agent_entries(roster, goal)

    used_avatars = {int(agent["avatar"]) for agent in active_entries if isinstance(agent.get("avatar"), int)}
    main_avatar = avatar_for_status(roster_status, sample_avatar(used_avatars))
    main_entry = {
        "id": "agent-main",
        "name": "主程式",
        "task": goal,
        "status": roster_status,
        "zone": visual_zone_for_status(roster_status),
        "avatar": main_avatar,
        "active": True,
    }

    agents = [main_entry]
    if active_entries:
        agents.extend(active_entries)

    blocked = extract_blocked(progress_text, roster)
    active_items = extract_active_items(roster, goal)

    return {
        "status": roster_status,
        "goal": goal,
        "progress": progress,
        "active": active_items,
        "blocked": blocked,
        "agents": agents,
        "completedAtByTaskId": {},
        "visibleTaskCount": len(active_items),
        "restTaskCount": 0,
        "hiddenTaskCount": 0,
        "doneTaskCount": 0,
        "totalTaskCount": len(active_items),
        "visibleAgentCount": len(agents),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_js(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        "window.MISSION_CENTER_STATE = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def write_embedded_state(html_path: Path, state_json: str) -> None:
    if not html_path.exists():
        return

    text = read_text(html_path)
    start_marker = "<!-- MISSION_CENTER_STATE_START -->"
    end_marker = "<!-- MISSION_CENTER_STATE_END -->"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return

    before = text[: start + len(start_marker)]
    after = text[end:]
    block = f"\n  <script id=\"mission-center-state\" type=\"application/json\">\n{state_json}\n  </script>\n"
    html_path.write_text(before + block + after, encoding="utf-8")


def main() -> int:
    mission_dir = Path(__file__).resolve().parent

    project_text = safe_text(mission_dir / "project.md")
    tasks_text = safe_text(mission_dir / "tasks.md")
    progress_text = safe_text(mission_dir / "progress.md")
    previous_state = load_previous_state(mission_dir / "visual-state.json")

    state = build_task_state(project_text, tasks_text, previous_state)
    if not state:
        roster = read_roster(mission_dir)
        state = legacy_task_state(project_text, progress_text, roster)

    state_json = json.dumps(state, ensure_ascii=False, indent=2)

    write_json(mission_dir / "visual-state.json", state)
    write_js(mission_dir / "visual-state.js", state)
    write_embedded_state(mission_dir / "command-center.html", state_json)

    visible_roles = len(state["agents"])
    print(f"MissionCenter visual state updated: {state['status']} ({visible_roles} visible roles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
