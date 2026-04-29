
    const panel = document.querySelector(".mission-panel");
    const goal = document.querySelector("#goal");
    const progressText = document.querySelector("#progressText");
    const stageText = document.querySelector("#stageText");
    const progressBar = document.querySelector("#progressBar");
    const statusText = document.querySelector("#statusText");
    const blockedText = document.querySelector("#blockedText");
    const activeList = document.querySelector(".task-card ul");
    const agentsLayer = document.querySelector(".agents-layer");
    const constructionSite = document.querySelector(".construction-site");
    const monument = document.querySelector("#monument");
    const stageArt = document.querySelector("#stageArt");
      const validStatuses = new Set(["Intake", "In Progress", "Blocked", "Review", "Done"]);
      const helperAvatarLimit = 16;
    const maxActiveItems = 6;
    const avatarAssignments = new Map();
    const helperAtlases = {
      1: "mission-helper-roster-8-fixed.png",
      2: "mission-helper-roster-8-girls-2.png"
    };
    const statusAliases = {
      Intake: "Intake",
      Ready: "Intake",
      Backlog: "Blocked",
      "In Progress": "In Progress",
      Blocked: "Blocked",
      Review: "Review",
      Done: "Done"
    };
    const rosterLayouts = {
      Intake: { x: 8.5, y: 22.6, width: 31.5, height: 18.8 },
      "In Progress": { x: 58.2, y: 22.6, width: 31.8, height: 24.4 },
      Blocked: { x: 8.5, y: 52.0, width: 31.5, height: 17.8 },
      Review: { x: 58.0, y: 52.4, width: 31.2, height: 17.8 },
      Done: { x: 25.8, y: 72.2, width: 48.4, height: 12.0 }
    };
    const zoneSlots = {
      Intake: [
        { x: 18, y: 28 }, { x: 24, y: 31 }, { x: 31, y: 28 }, { x: 26, y: 36 }
      ],
      "In Progress": [
        { x: 64, y: 30 }, { x: 70, y: 33 }, { x: 76, y: 30 }, { x: 71, y: 38 }
      ],
      Blocked: [
        { x: 18, y: 58 }, { x: 24, y: 61 }, { x: 31, y: 58 }, { x: 26, y: 66 }
      ],
      Review: [
        { x: 64, y: 58 }, { x: 70, y: 61 }, { x: 76, y: 58 }, { x: 71, y: 66 }
      ],
      Done: [
        { x: 28, y: 78 }, { x: 38, y: 80 }, { x: 48, y: 78 }, { x: 58, y: 80 }
      ]
    };
    let currentAgents = [];

    function clamp(value, min, max) {
      return Math.min(max, Math.max(min, value));
    }

    function spriteInfoForAvatar(avatar) {
      const normalized = Math.max(1, Math.min(helperAvatarLimit, Number(avatar) || 1));
      const atlas = normalized <= 8 ? helperAtlases[1] : helperAtlases[2];
      const rowIndex = (normalized - 1) % 8;
      return {
        atlas,
        rowY: `${(rowIndex / 7) * 100}%`
      };
    }

    function pickRandomAvatar(id, usedAvatars) {
      if (avatarAssignments.has(id)) return avatarAssignments.get(id);

      const available = Array.from({ length: helperAvatarLimit }, (_, index) => index + 1)
        .filter((avatar) => !usedAvatars.has(avatar));
      const pool = available.length ? available : Array.from({ length: helperAvatarLimit }, (_, index) => index + 1);
      const avatar = pool[Math.floor(Math.random() * pool.length)];
      avatarAssignments.set(id, avatar);
      usedAvatars.add(avatar);
      return avatar;
    }

    function normalizeAgent(agent, index, fallbackStatus, usedAvatars) {
      const status = validStatuses.has(agent?.status) ? agent.status : fallbackStatus;
      const id = agent?.id || `agent-${index + 1}`;
      const explicitAvatar = Number(agent?.avatar);
      const avatar = Number.isFinite(explicitAvatar) && explicitAvatar > 0
        ? Math.max(1, Math.min(helperAvatarLimit, explicitAvatar))
        : pickRandomAvatar(id, usedAvatars);
      usedAvatars.add(avatar);
      return {
        id,
        name: agent?.name || `Agent ${index + 1}`,
        task: agent?.task || status,
        status,
        avatar
      };
    }

    function renderMonument(progress) {
      const stage = Math.max(0, Math.min(10, Math.ceil(progress / 10)));
      stageArt.src = "mission-base-main.png";
      stageArt.alt = "MissionCenter high-tech base";
      constructionSite.dataset.stage = String(stage);
      stageText.textContent = `${stage}/10`;
      monument.innerHTML = Array.from({ length: 10 }, (_, index) => {
        const level = 9 - index;
        const built = index < stage ? " is-built" : "";
        return `<div class="monument-block${built}" style="--level: ${level};"></div>`;
      }).join("") + '<div class="meme-face"><div class="meme-mouth"></div></div>';
    }

    function renderAgents(state, fallbackStatus) {
      const rawAgents = Array.isArray(state.agents) && state.agents.length
        ? state.agents
        : [{ id: "main", name: "MissionHelper", status: fallbackStatus, task: state.goal }];
      const usedAvatars = new Set();
      const slotCounts = new Map();
      currentAgents = rawAgents.map((agent, index) => normalizeAgent(agent, index, fallbackStatus, usedAvatars));
      const scale = currentAgents.length > 16 ? 0.62 : currentAgents.length > 12 ? 0.72 : currentAgents.length > 6 ? 0.82 : 1;

      agentsLayer.innerHTML = currentAgents.map((agent) => {
        const pos = pickSlot(agent.status, slotCounts);
        const label = `${agent.name}: ${agent.task}`;
        const sprite = spriteInfoForAvatar(agent.avatar);

        return `
          <div class="agent" data-id="${escapeAttr(agent.id)}" data-status="${escapeAttr(agent.status)}" data-avatar="${agent.avatar}" data-slot-x="${pos.x}" data-slot-y="${pos.y}" style="--sheet: url('${sprite.atlas}'); --row-y: ${sprite.rowY}; --x: ${pos.x}%; --y: ${pos.y}%; --scale: ${scale};">
            <div class="sprite"></div>
            <div class="nameplate">${escapeHtml(label)}</div>
          </div>
        `;
      }).join("");
    }

    function readEmbeddedState() {
      const node = document.querySelector("#mission-center-state");
      if (!node) return null;
      try {
        return JSON.parse(node.textContent || "null");
      } catch {
        return null;
      }
    }

    function wanderAgents() {
      currentAgents.forEach((agent) => {
        const node = agentsLayer.querySelector(`[data-id="${cssEscape(agent.id)}"]`);
        if (!node) return;
        const baseX = Number(node.dataset.slotX || 0);
        const baseY = Number(node.dataset.slotY || 0);
        const jitterX = round((Math.random() * 4) - 2);
        const jitterY = round((Math.random() * 3) - 1.5);
        node.style.setProperty("--x", `${round(baseX + jitterX)}%`);
        node.style.setProperty("--y", `${round(baseY + jitterY)}%`);
      });
    }

    function pickSlot(status, slotCounts) {
      const slots = zoneSlots[status] || zoneSlots.Intake;
      const count = slotCounts.get(status) || 0;
      slotCounts.set(status, count + 1);
      const base = slots[count % slots.length];
      const ring = Math.floor(count / slots.length);
      const wobble = ring * 1.6;
      return {
        x: round(base.x + (count % 2 === 0 ? wobble : -wobble)),
        y: round(base.y + (count % 3 === 0 ? wobble : -wobble * 0.5))
      };
    }

    async function loadState() {
      try {
        const state = readEmbeddedState() || window.MISSION_CENTER_STATE || await (async () => {
          const response = await fetch(`visual-state.json?ts=${Date.now()}`, { cache: "no-store" });
          if (!response.ok) return null;
          return response.json();
        })();
        if (!state) return;
        const status = validStatuses.has(state.status) ? state.status : "Intake";
        const progress = Math.max(0, Math.min(100, Number(state.progress) || 0));

        panel.dataset.status = status;
        goal.textContent = state.goal || "MissionCenter task";
        progressText.textContent = `${progress}%`;
        progressBar.style.width = `${progress}%`;
        statusText.textContent = status;
        const activeItems = Array.isArray(state.active) ? state.active : [];
        const visibleItems = activeItems.slice(0, maxActiveItems);
        const hiddenCount = Math.max(0, activeItems.length - visibleItems.length);
        activeList.innerHTML = visibleItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
          + (hiddenCount ? `<li>+${hiddenCount} more</li>` : "");
        blockedText.textContent = `Blocked: ${(state.blocked || []).join(", ") || "None"}`;
        renderMonument(progress);
        renderAgents(state, status);
      } catch {
        // File URLs and local browser cache can occasionally race during writes.
      }
    }

    function round(value) {
      return Math.round(value * 10) / 10;
    }

    function cssEscape(value) {
      if (window.CSS?.escape) return CSS.escape(String(value));
      return String(value).replace(/["\\]/g, "\\$&");
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, "&#96;");
    }

    loadState();
    setInterval(loadState, 10000);
    setInterval(wanderAgents, 6500);
