# CloudHime UI i18n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight `English / 繁中` UI language selector beside the theme selector, centralize the most visible UI strings, and keep OCR/translation output language aligned with the chosen UI language.

**Architecture:** Introduce one small localization layer that owns UI language state, string lookup, and fallback behavior. Persist the selected UI language in settings, load it at startup, and let the translation workflow reuse the same target-language choice so Google and AI translation behave consistently.

**Tech Stack:** Python 3.10+, PySide6, existing `settings_store.py`, existing translation providers, MissionCenter task tracking, headless Chrome smoke test for the settings dialog and main window.

---

### Task 1: Add settings-backed UI language state

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/settings_store.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/CloudHime.py`

- [ ] **Step 1: Confirm current settings schema and load/save path**

Read the current settings payload in `CloudHime.py` and verify where `theme_mode`, `google_api_key`, and translation flags are saved.

- [ ] **Step 2: Add `ui_language` to the persisted settings payload**

Store the selected UI language as a plain string value such as `en` or `zh-TW`, defaulting to `en` when missing.

- [ ] **Step 3: Load `ui_language` during startup**

During app bootstrap, read the saved language, normalize unknown values to `en`, and keep the chosen value on the controller for later UI refresh.

- [ ] **Step 4: Run a syntax check**

Run: `python -m py_compile CloudHime.py settings_store.py`

Expected: no syntax errors.

### Task 2: Add a small localization layer

**Files:**
- Create: `C:/Users/USER/MyPython/CloudHime/localization.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/CloudHime.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/translation_settings_panel.py`

- [ ] **Step 1: Define the translation keys that the UI needs first**

Create a compact string catalog for the current app chrome: settings labels, main status text, translation mode labels, and the language dropdown labels.

- [ ] **Step 2: Implement a tiny `tr(key)` helper with fallback**

Return English when a key or language is missing, and return the raw key only as a last resort so the UI never crashes on missing text.

- [ ] **Step 3: Add a method to refresh visible widget text after language changes**

Make the main window and settings panel re-read localized labels without reconstructing the whole window.

- [ ] **Step 4: Run a syntax check**

Run: `python -m py_compile CloudHime.py localization.py translation_settings_panel.py`

Expected: no syntax errors.

### Task 3: Place the UI language dropdown beside the theme selector

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/CloudHime.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/translation_settings_panel.py`

- [ ] **Step 1: Add the `English / 繁中` dropdown**

Place the new combo box in the settings header row next to the color mode control, reusing the existing spacing so the panel does not grow a new section.

- [ ] **Step 2: Wire the dropdown to controller state**

Changing the dropdown should update controller state, refresh visible labels, and schedule a settings save.

- [ ] **Step 3: Restore the saved selection on open**

When the settings panel opens, it should show the last saved UI language rather than resetting to the default.

- [ ] **Step 4: Run a quick layout smoke check**

Open the settings window and verify the theme selector and language selector fit on one line without clipping.

### Task 4: Align translation output language with the UI language

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/translation_providers.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/translation_helpers.py`
- Modify: `C:/Users/USER/MyPython/CloudHime/CloudHime.py`

- [ ] **Step 1: Map UI language to translation target language**

Make `en` map to English output and `zh-TW` map to Traditional Chinese output so the same setting drives both UI and scan translation defaults.

- [ ] **Step 2: Keep Google and Gemini flows consistent**

Ensure the Google translation button and AI translation mode both read the same target-language state, so the UI does not imply one language while the output uses another.

- [ ] **Step 3: Keep OCR scan result labels localized**

Update status text and result summaries so scan feedback uses the selected UI language instead of mixing English and Chinese strings.

- [ ] **Step 4: Run a runtime sanity check**

Run the app, perform one OCR translation in each language, and verify the output target language matches the selector.

### Task 5: Refresh smoke tests and docs

**Files:**
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/smoke-tests.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/progress.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/snapshot.md`
- Modify: `C:/Users/USER/MyPython/CloudHime/MissionCenter/project.md`

- [ ] **Step 1: Add a language-switch smoke test**

Record the exact expected behavior for switching `English / 繁中`, reopening the settings window, and confirming the choice persists.

- [ ] **Step 2: Update the MissionCenter progress summary**

Move the i18n work into the active-progress section and keep the blocked items honest.

- [ ] **Step 3: Record one checkpoint snapshot**

Capture the new state once the dropdown and localization helper are in place, even if only part of the text table is converted.

- [ ] **Step 4: Commit the finished slice**

Use a small commit that contains only the language selector, localization helper, and the related smoke-test updates.

---

**Coverage check**

- UI language storage: Task 1
- String lookup and fallback: Task 2
- Settings page dropdown placement: Task 3
- Translation output alignment: Task 4
- MissionCenter tracking and verification: Task 5

