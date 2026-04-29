from __future__ import annotations

import json
import random
import re
from pathlib import Path


HELPER_AVATAR_LIMIT = 16
VALID_STATUSES = {"Intake", "In Progress", "Blocked", "Review", "Done"}
RNG = random.SystemRandom()

HEADER_ALIASES = {
    "ID": "ID",
    "編號": "ID",
    "Title": "Title",
    "標題": "Title",
    "Type": "Type",
    "類型": "Type",
    "Parent": "Parent",
    "上層": "Parent",
    "Priority": "Priority",
    "優先級": "Priority",
    "Status": "Status",
    "狀態": "Status",
    "Owner": "Owner",
    "負責人": "Owner",
    "Depends on": "Depends on",
    "依賴": "Depends on",
    "Next action": "Next action",
    "下一步": "Next action",
    "Verification": "Verification",
    "驗證": "Verification",
    "Estimate": "Estimate",
    "預估": "Estimate",
    "Labels": "Labels",
    "標籤": "Labels",
    "Comments": "Comments",
    "備註": "Comments",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_after_colon(line: str) -> str:
    if ":" in line:
        return line.split(":", 1)[1].strip()
    if "：" in line:
        return line.split("：", 1)[1].strip()
    return ""


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return rows

    header = [HEADER_ALIASES.get(cell.strip(), cell.strip()) for cell in lines[0].strip("|").split("|")]
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        if row.get("ID", "").startswith("CH-"):
            rows.append(row)
    return rows


def extract_goal(project_text: str) -> str:
    fallback = "CloudHime demo readiness and commercialization"
    for line in project_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Goal:") or stripped.startswith("- 目標:") or stripped.startswith("- 目標："):
            value = split_after_colon(stripped)
            return value or fallback
        if stripped.startswith("- Objective:") or stripped.startswith("- 目標 / Objective:"):
            value = split_after_colon(stripped)
            return value or fallback
    return fallback


def extract_status(progress_text: str) -> str:
    for line in progress_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Current status:") or stripped.startswith("- 目前狀態:") or stripped.startswith("- 目前狀態："):
            value = split_after_colon(stripped)
            value = re.split(r"[|｜]", value, maxsplit=1)[0].strip()
            return value or "Intake"
    return "Intake"


def extract_progress(progress_text: str) -> int:
    match = re.search(r"(\d{1,3})%", progress_text)
    if match:
        return max(0, min(100, int(match.group(1))))
    return 0


def extract_blocked(progress_text: str) -> list[str]:
    blocked: list[str] = []
    in_blocked = False
    for raw_line in progress_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## Blocked By") or line.startswith("## 阻塞項"):
            in_blocked = True
            continue
        if in_blocked and line.startswith("## "):
            break
        if in_blocked and line.startswith("- "):
            item = line[2:].strip()
            if item:
                blocked.append(item)
    return blocked or ["None"]


def infer_active_tasks(tasks: list[dict[str, str]]) -> list[str]:
    active = [
        task.get("Title", task.get("ID", ""))
        for task in tasks
        if task.get("Status") in {"Ready", "In Progress", "Review"}
    ]
    if not active:
        active = [
            task.get("Title", task.get("ID", ""))
            for task in tasks
            if task.get("Status") not in {"Done", "Backlog"}
        ]
    return active[:3]


def infer_worker_tasks(tasks: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        task
        for task in tasks
        if task.get("Status") in {"In Progress", "Review"}
    ]


def alpha_label(index: int) -> str:
    label = ""
    value = index
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


def sample_avatar(used_avatars: set[int]) -> int:
    available = [avatar for avatar in range(1, HELPER_AVATAR_LIMIT + 1) if avatar not in used_avatars]
    if available:
        avatar = RNG.choice(available)
    else:
        avatar = RNG.randint(1, HELPER_AVATAR_LIMIT)
    used_avatars.add(avatar)
    return avatar


def build_agents(status: str, goal: str, tasks: list[dict[str, str]]) -> list[dict[str, str | int]]:
    agents: list[dict[str, str | int]] = [
        {
            "id": "agent-main",
            "name": "主程式",
            "status": status,
            "task": goal,
            "avatar": sample_avatar(set()),
        }
    ]

    worker_tasks = infer_worker_tasks(tasks)
    used_avatars = {int(agents[0]["avatar"])}
    for index, task in enumerate(worker_tasks, start=1):
        agents.append(
            {
                "id": f"agent-{index}",
                "name": f"代理{alpha_label(index)}",
                "status": task.get("Status", "In Progress"),
                "task": task.get("Title", task.get("ID", f"Task {index}")),
                "avatar": sample_avatar(used_avatars),
            }
        )
    return agents


def write_embedded_state(html_path: Path, state_json: str) -> None:
    if not html_path.exists():
        return

    html_text = read_text(html_path)
    start_marker = "<!-- MISSION_CENTER_STATE_START -->"
    end_marker = "<!-- MISSION_CENTER_STATE_END -->"
    if start_marker not in html_text or end_marker not in html_text:
        return

    start = html_text.index(start_marker) + len(start_marker)
    end = html_text.index(end_marker, start)
    embedded_block = (
        '\n  <script id="mission-center-state" type="application/json">\n'
        f"  {state_json}\n"
        "  </script>\n"
    )
    html_text = html_text[:start] + embedded_block + html_text[end:]
    html_path.write_text(html_text, encoding="utf-8")


def main() -> int:
    root = Path(".").resolve() / "MissionCenter"
    tasks_path = root / "tasks.md"
    progress_path = root / "progress.md"
    project_path = root / "project.md"
    html_path = root / "command-center.html"
    out_json_path = root / "visual-state.json"
    out_js_path = root / "visual-state.js"

    tasks = parse_markdown_table(read_text(tasks_path))
    progress_text = read_text(progress_path)
    project_text = read_text(project_path)

    status = extract_status(progress_text)
    goal = extract_goal(project_text)
    progress = extract_progress(progress_text)
    active = infer_active_tasks(tasks)
    blocked = extract_blocked(progress_text)
    agents = build_agents(status, goal, tasks)

    state = {
        "status": status,
        "goal": goal,
        "progress": progress,
        "active": active,
        "blocked": blocked,
        "agents": agents,
    }

    state_json = json.dumps(state, ensure_ascii=False, indent=2)
    out_json_path.write_text(state_json, encoding="utf-8")
    out_js_path.write_text(f"window.MISSION_CENTER_STATE = {state_json};\n", encoding="utf-8")
    write_embedded_state(html_path, state_json)
    print(f"MissionCenter visual state updated: {status} ({len(agents)} visible roles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
