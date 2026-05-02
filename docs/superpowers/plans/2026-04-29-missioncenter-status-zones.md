# MissionCenter 狀態區域與自動監控調整實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 MissionCenter HUD 只顯示現役 AGENT，並依大狀態自動移動到對應工作區；`Waiting` 視覺上併入 `Done` 休息區，真正完成時子 AGENT 退場。

**Architecture:** 以 `MissionCenter/active-agents.json` 作為現役 roster 的資料來源，保留 `active` 標記但不再用細工作細節驅動視覺。`sync_visual_state.py` 負責把 roster 與任務狀態轉成 `visual-state.json/js`，`watch_visual_state.py` 負責監控來源檔變更並自動重跑同步，`command-center.html` 只讀最新視覺狀態並把角色平滑移到對應大區域。視覺上維持五大區域，但 `Waiting` 的視覺表現併入 `Done` 區，`Done` 且 `active=false` 的角色不再出現在 HUD。

**Tech Stack:** Python 3、HTML/CSS/JavaScript、Windows file watching via polling、現有 MissionCenter Markdown 檔案。

---

### Task 1: 定義現役 roster 與等待/退場規則

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/active-agents.json`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/decisions.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/notes.md`

- [ ] **Step 1: 先把 roster 規則寫進決策檔**

```md
| 2026-04-29 | Waiting 視覺併入 Done 區，Done=休息區，真正完成時 active=false 退場 | HUD 只保留大區域，不再加細工作節點 | 小人行為更簡潔，完成後會從地圖上消失 |
```

- [ ] **Step 2: 重寫 roster 範例資料**

```json
{
  "agents": [
    {
      "id": "agent-main",
      "name": "主程式",
      "status": "In Progress",
      "task": "CloudHime demo 與 MissionCenter 維修",
      "active": true
    },
    {
      "id": "agent-1",
      "name": "子AGENT",
      "status": "In Progress",
      "task": "目前進行中的子工作",
      "active": true
    },
    {
      "id": "agent-2",
      "name": "Curie",
      "status": "Done",
      "task": "已完成後退場",
      "active": false
    }
  ]
}
```

- [ ] **Step 3: 在 notes 補上新規則**

```md
- `Waiting` 視覺上併入 `Done` 休息區。
- `Done` 只代表真正完成，完成後該角色會從 HUD 退場。
```

- [ ] **Step 4: 用 JSON 讀回驗證 roster 格式**

```bash
@'
import json, pathlib
obj = json.loads(pathlib.Path("MissionCenter/active-agents.json").read_text(encoding="utf-8-sig"))
assert any(a["active"] for a in obj["agents"])
print("roster ok")
'@ | python -
```

**Expected:** `roster ok`

### Task 2: 讓同步腳本支援等待區與退場邏輯

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/sync_visual_state.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/visual-state.json`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/visual-state.js`

- [ ] **Step 1: 寫同步規則測試**

```python
def test_status_to_visual_zone_maps_waiting_to_done():
    assert visual_zone_for_status("Waiting") == "Done"
    assert visual_zone_for_status("Done") == "Done"
    assert visual_zone_for_status("In Progress") == "In Progress"
```

- [ ] **Step 2: 重新跑同步時排除 inactive 角色**

```python
active_agents = [agent for agent in agents_data if agent.get("active")]
```

- [ ] **Step 3: 加入狀態映射**

```python
STATUS_ZONE_MAP = {
    "Intake": "Intake",
    "In Progress": "In Progress",
    "Blocked": "Blocked",
    "Review": "Review",
    "Waiting": "Done",
    "Done": "Done",
}
```

- [ ] **Step 4: 同步輸出後驗證**

```bash
python MissionCenter/sync_visual_state.py
@'
import json, pathlib
obj = json.loads(pathlib.Path("MissionCenter/visual-state.json").read_text(encoding="utf-8"))
print(len(obj["agents"]))
print([a["status"] for a in obj["agents"]])
'@ | python -
```

**Expected:** 現役數量只包含 `active=true` 角色，`Waiting` 會映射到 `Done` 視覺區。

### Task 3: 調整 HUD 的區域移動與退場表現

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/command-center.html`

- [ ] **Step 1: 寫 HUD 位置規則測試**

```js
function testZoneForStatus() {
  console.assert(zoneForStatus("Waiting").name === "Done");
  console.assert(zoneForStatus("Done").name === "Done");
}
```

- [ ] **Step 2: 把 Waiting 的視覺併入 Done 區**

```js
const statusAliases = {
  Intake: "Intake",
  Ready: "Intake",
  Backlog: "Blocked",
  "In Progress": "In Progress",
  Blocked: "Blocked",
  Review: "Review",
  Waiting: "Done",
  Done: "Done"
};
```

- [ ] **Step 3: 讓角色改狀態時平滑走向新大區域**

```js
if (agent.status && motion.zone !== agent.status) {
  motion.zone = agent.status;
  motion.nextWanderAt = now + 1200;
  const nextPoint = randomPointInArea(zoneForStatus(agent.status), 0.18);
  motion.targetX = nextPoint.x;
  motion.targetY = nextPoint.y;
}
```

- [ ] **Step 4: 讓真正 Done 的 inactive 角色不再渲染**

```js
const rawAgents = Array.isArray(state.agents)
  ? state.agents.filter((agent) => agent.active !== false)
  : [];
```

- [ ] **Step 5: 重新整理 Done 休息區文案與基地圖說明**

```md
Done 區 = 休息區 / 收工區，等待完成後會在這裡停一下。
```

### Task 4: 更新自動監控器的觸發範圍與文件

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/watch_visual_state.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/visual-hub.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/smoke-tests.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/progress.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/snapshot.md`

- [ ] **Step 1: 讓 watcher 持續盯住 roster 與任務檔**

```python
WATCHED_FILES = (
    "active-agents.json",
    "project.md",
    "progress.md",
    "tasks.md",
)
```

- [ ] **Step 2: 更新視覺指揮中心說明**

```md
- `Waiting` 會被併到 `Done` 的休息區。
- 真正完成後，inactive 角色會從 HUD 退場。
```

- [ ] **Step 3: 補上可重跑 smoke test**

```md
| 自動監控同步 | 啟動 `watch_visual_state.py` 後把某角色標成 inactive | HUD 會自動刷新且人數減少 | Pass/Fail |
```

- [ ] **Step 4: 更新進度與 snapshot**

```md
- 活躍 roster：依 active=true 計算
- Done 區：包含 waiting/休息中的角色視覺表現
```

**Expected:** 文件反映新規則，HUD 更新說明不再和實作打架。

### Task 5: 驗證、啟動 watcher、觀察退場

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/visual-state.json`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/command-center.html`

- [ ] **Step 1: 執行同步與語法檢查**

```bash
python -m py_compile MissionCenter/sync_visual_state.py MissionCenter/watch_visual_state.py
python MissionCenter/sync_visual_state.py
node -e "const fs=require('fs'); const html=fs.readFileSync('MissionCenter/command-center.html','utf8'); const scripts=[...html.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)].map(m=>m[1]); new Function(scripts[scripts.length-1]); console.log('JS syntax OK')"
```

- [ ] **Step 2: 啟動 watcher 並確認進程存在**

```bash
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList '.\\MissionCenter\\watch_visual_state.py'
```

- [ ] **Step 3: 切一個角色到 Waiting，再切成 Done 並 inactive**

```json
{
  "id": "agent-1",
  "name": "子AGENT",
  "status": "Waiting",
  "active": true
}
```

```json
{
  "id": "agent-1",
  "name": "子AGENT",
  "status": "Done",
  "active": false
}
```

- [ ] **Step 4: 在 in-app browser 看結果**

```text
Waiting 時：角色停在 Done 休息區
Done 且 inactive：角色從地圖退場
```

**Expected:** HUD 會自動跟上檔案變更，等待中的角色留在休息區，完成後消失。
