---
name: CloudHime
description: Windows 原生 OCR 與即時翻譯的三欄夢幻設定介面視覺系統
colors:
  light-shell: "rgba(242, 242, 247, 235)"
  light-panel: "rgba(255, 255, 255, 240)"
  light-input: "rgba(255, 255, 255, 200)"
  light-text: "#1C1C1E"
  light-subtext: "#8E8E93"
  light-border: "rgba(0, 0, 0, 15)"
  light-accent: "#007AFF"
  settings-top-light: "#F2F2F7"
  dark-shell: "rgba(28, 28, 30, 242)"
  dark-panel: "rgba(44, 44, 46, 230)"
  dark-input: "rgba(118, 118, 128, 60)"
  dark-text: "rgba(255, 255, 255, 220)"
  dark-subtext: "rgba(235, 235, 245, 150)"
  dark-border: "rgba(255, 255, 255, 20)"
  dark-accent: "#0A84FF"
  settings-top-dark: "#1C1C1E"
  high-contrast-fallback: "rgba(18, 18, 18, 248)"
  high-contrast-accent: "#FFD400"
  provider-metadata-light: "#636366"
  provider-metadata-dark: "#E5E5EA"
  provider-metadata-high-contrast: "#FFFFFF"
  on-accent: "#FFFFFF"
  cooldown-amber: "#F4C542"
  error-red: "#E53935"
typography:
  display:
    fontFamily: "Bahnschrift SemiBold, Microsoft JhengHei UI"
    fontSize: "20px"
    fontWeight: 900
  headline:
    fontFamily: "Bahnschrift SemiBold, Microsoft JhengHei UI"
    fontSize: "18px"
    fontWeight: 800
  title:
    fontFamily: "Microsoft JhengHei UI, Bahnschrift SemiBold"
    fontSize: "14px"
    fontWeight: 800
  body:
    fontFamily: "Microsoft JhengHei UI"
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: "Microsoft JhengHei UI"
    fontSize: "12px"
    fontWeight: 700
  provider:
    fontFamily: "Microsoft JhengHei UI"
    fontSize: "13px"
    fontWeight: 700
  provider-metadata:
    fontFamily: "Microsoft JhengHei UI"
    fontSize: "10px"
    fontWeight: 400
rounded:
  input: "6px"
  nested: "8px"
  control: "10px"
  panel: "14px"
  shell: "20px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  control: "10px"
  section: "14px"
  card-vertical: "10px"
  card-horizontal: "18px"
  translation-top: "16px"
  translation-horizontal: "20px"
  translation-bottom: "18px"
  shell-horizontal: "22px"
components:
  button-primary-light:
    backgroundColor: "{colors.light-accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.nested}"
    padding: "10px 18px"
    height: "32px"
  button-primary-dark:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.nested}"
    padding: "10px 18px"
    height: "32px"
  button-secondary-light:
    backgroundColor: "{colors.light-input}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
    height: "32px"
  button-secondary-dark:
    backgroundColor: "{colors.dark-input}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
    height: "32px"
  input-light:
    backgroundColor: "{colors.light-input}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.input}"
    padding: "7px"
    height: "32px"
  input-dark:
    backgroundColor: "{colors.dark-input}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.input}"
    padding: "7px"
    height: "32px"

---

# Design System: CloudHime

## Overview

**Creative North Star: "Legacy Dream Window／舊版夢幻設定窗"**

CloudHime 的 shipping UI 是 Windows 原生設定窗與全幅角色夢境的並置：角色與雲景提供 light／dark 的環境溫度，真正承載操作的是半透明、可讀、近等寬的三欄工作面。介面保持原版設定窗的密度與順序，讓使用者一眼找到 Translation、OCR、Rendering 與 Relief，而不是把設定改寫成另一套產品殼層。

這個世界的辨識度來自全幅背景、固定的 opaque header band、固定 footer，以及柔和的面板與原生 Qt controls。Translation card 內部可以局部垂直捲動，容納 Local Gemma、Online Gemma 與 Luna 的設定；Online Gemma 使用同一把 API key，並在內部列出兩個實際模型。這份文件描述 Git 舊版復原後的 shipping surface，不採新版 navy dispatch、左側導覽或單欄工作面。

**Key Characteristics:**
- Wide fixed settings surface 搭配全幅 light／dark 角色背景，操作層維持半透明但可讀
- Opaque header band 與固定 footer 維持全寬並保持在工作面前景
- 透明 body host 左對齊，內容 cluster 寬度限制在 928–1040px
- Translation／OCR／Rendering+Relief 三欄近等寬、每欄至少 300px、欄間距 14px
- 右側保留角色 safe area（至少約 280px；1422px capture 實際約 419px）
- Translation card 內部垂直 scroll；Online Gemma 單 key 雙模型並與 Luna 同處 Translation
- 形狀柔和、邊界細緻、狀態文字清楚；不以裝飾取代操作資訊

Shipping artifacts 是 `cloudhime_ui.py`、`translation_settings_panel.py` 與 `themes.py`。最新 provider polish evidence 是 `.impeccable/review/provider-polish-collapsed-light.png`、`.impeccable/review/provider-polish-collapsed-dark.png`、`.impeccable/review/provider-polish-online-expanded-light.png`、`.impeccable/review/provider-polish-online-expanded-dark.png`、`.impeccable/review/provider-polish-luna-expanded-dark.png`；視覺參照為 `MissionCenter/settings-fresh-light-real.png` 與 `MissionCenter/settings-fresh-dark-real.png`。

## Colors

Light 以 `#F2F2F7` 的冷霧 shell 和白色 panel 承載內容；Dark 以 `#1C1C1E` 的不透明 top band、深色 shell 與半透明 graphite panel 保持夜間對比。藍色只作互動與選取焦點，琥珀與紅色只作等待／錯誤語意。

### Primary
- **System Blue Light** (`#007AFF`): Light 主按鈕、選取、focus 與可互動的狀態標記。
- **System Blue Dark** (`#0A84FF`): Dark 主按鈕、選取與 focus 語意。

### Secondary
- **Cooldown Amber** (`#F4C542`): 等待、quota／cooldown 或 loading 狀態；只有有證據的狀態才顯示數字。

### Tertiary
- **Error Red** (`#E53935`): provider error／failed 語意；不作一般裝飾。

### Neutral
- **Light Shell** (`rgba(242, 242, 247, 235)`): Light 背景與視窗外殼。
- **Light Panel** (`rgba(255, 255, 255, 240)`): Light card／工作面。
- **Light Input** (`rgba(255, 255, 255, 200)`): Light 欄位與次要 controls。
- **Light Text** (`#1C1C1E`)：Light 主要文字；輔助文字使用 `#8E8E93`。
- **Dark Shell** (`rgba(28, 28, 30, 242)`): Dark 背景與視窗外殼。
- **Dark Panel** (`rgba(44, 44, 46, 230)`): Dark card／工作面。
- **Dark Input** (`rgba(118, 118, 128, 60)`): Dark 欄位與次要 controls。
- **Dark Text** (`rgba(255, 255, 255, 220)`)：Dark 主要文字；輔助文字使用 `rgba(235, 235, 245, 150)`。
- **Settings Top Light** (`#F2F2F7`): Light opaque header band。
- **Settings Top Dark** (`#1C1C1E`): Dark opaque header band。
- **High-contrast Fallback** (`rgba(18, 18, 18, 248)`): 高對比或背景圖不可用時的操作底色；高對比 accent 為 `#FFD400`。

### Named Rules

**The Semantic Accent Rule.** 藍色、琥珀與紅色只承擔互動或狀態語意；不要把狀態色鋪成背景裝飾。

## Typography

**Display Font:** Bahnschrift SemiBold (with Microsoft JhengHei UI fallback)
**Body Font:** Microsoft JhengHei UI (with Bahnschrift SemiBold available for Windows headings)
**Label/Mono Font:** Microsoft JhengHei UI for labels and provider metadata

**Character:** Bahnschrift SemiBold 帶出 Windows chrome 的清楚輪廓，Microsoft JhengHei UI 確保繁中、英文與 provider metadata 在高 DPI 下仍易讀。標題有辨識度，但資訊密度優先於展示性。

### Hierarchy
- **Display** (900, 20px): Settings 主標題與 Translation／OCR／Rendering section heading。
- **Headline** (800, 18px): 次要視窗或 compact HUD 標題。
- **Title** (800, 14px): Relief、Provider 與控制區的短標題。
- **Body** (400, 13px): 欄位值、按鈕文字與一般設定內容。
- **Provider** (700, 13px): Provider 名稱，作為每個 disclosure header 的主要識別。
- **Status / Detail / Capability** (400–700, 約 10–11px): provider 狀態、細節、能力與 scope metadata；依主題使用對比 token，在 Light／Dark／High Contrast 都必須可讀。

### Named Rules

**The Windows Pairing Rule.** 顯示文字使用 Bahnschrift SemiBold 搭配 Microsoft JhengHei UI；不要使用 bitmap 字、emoji glyph 或圖示字型取代可讀文字。

## Layout

基準 shipping capture 為 1422×800，SettingsWindowRevamp 是 wide fixed surface。外層使用 12px inset；header band 與 footer 維持全寬並位於前景。body 是透明 host，cluster 左對齊，寬度限制在 928px minimum 至 1040px maximum；1422px capture 右側保留約 419px 的角色 safe area，其他寬度也至少保留約 280px 的安全空間。

body cluster 是三欄近等寬 grid，三欄各至少 300px、欄間距與列間距皆為 14px，三欄 stretch 相同。Translation 在左欄跨兩列，OCR 在中欄跨兩列，Rendering 在右上、Relief 在右下；這是固定的舊版空間語法。header/footer 不受 cluster max-width 限制，也不加入 left navigation、illustration rail 或全頁單欄工作面。

Translation card 的內部 `QScrollArea` 關閉水平 scrollbar，只在 card 內容需要時顯示垂直 scrollbar；不存在包住整頁的 scroll。內容 inset 為 20px horizontal、16px top、18px bottom。它承接 Local Gemma、Online Gemma 與 Luna，Online Gemma 內含 `gemma-4-26b-a4b-it` 與 `gemma-4-31b-it` 兩個 model rows。窄高視窗可以捲動 Translation card，但不縮小文字層級或推走固定 footer。

## Elevation & Depth

深度由全幅 light／dark 角色背景、半透明 shell／panel、細邊界與 tonal layering 提供；背景只在操作層後方，不是內容。Settings backdrop 可以使用整體 ambient shadow（blur 30px、向下 10px、約 `rgba(0, 0, 0, 0.235)`），個別 card、provider row 與 control 不使用厚重 block shadow。高對比或背景圖不可用時回到不含插畫的 fallback surface。

### Shadow Vocabulary
- **Window ambient** (`0 10px 30px rgba(0, 0, 0, 0.235)`): 只抬起整個 Settings backdrop，避免套到每張卡或每個 provider row。

### Named Rules

**The Backdrop-Only Depth Rule.** 插畫與陰影只建立視窗氛圍；文字、API key、scroll、header、footer 與 controls 永遠在可讀的前景層。

## Shapes

外框是 20px 柔和圓角，設定 panel 是 14px，巢狀 provider／model frame 是 8px，常規 input 是 6px，按鈕約 8–10px，狀態摘要 pill 是 999px。邊界使用 1px theme-aware border；focus 使用 2px accent／focus border，不以 blur glow 取代焦點。全幅背景受 backdrop 邊界裁切，不能溢出內容層。

## Components

### Buttons
- **Shape:** 原生 QPushButton；footer primary 使用 8px 圓角，次要 controls 使用 8–10px。
- **Primary:** 依主題使用 System Blue（Light `#007AFF`、Dark `#0A84FF`）與白字；主要 footer action 使用 `10px 18px` padding、至少 32px 高度。
- **Hover / Focus:** hover 使用 theme control hover 或 accent-soft；focus 保留可見 2px accent border；checked 使用 accent 填色與白字；disabled 使用 disabled surface 與 quiet text。
- **Secondary / Ghost / Tertiary:** 次要按鈕使用 input／control surface 與 1px border；ghost 維持透明，只在 hover 顯示輕微 accent-soft。

### Cards / Containers
- **Corner Style:** backdrop 20px；四個主要設定 card 14px；Translation 內的 provider／model frame 8px。
- **Background:** Light 使用 translucent white panel；Dark 使用 translucent graphite panel；欄位使用 theme input surface。
- **Shadow Strategy:** 只有整體 backdrop 有 ambient shadow；cards 與 rows 以 border 和透明度分層。
- **Border:** 1px theme border；Translation／OCR／Rendering／Relief 依現行 surface accent 使用細色邊界。
- **Internal Padding:** 主要 card 約 18px horizontal／10px vertical；Translation content 20px horizontal／16–18px vertical。

### Inputs / Fields
- **Style:** theme input surface、1px border、6px radius、7px padding、至少 32px height；QComboBox 保留 22px dropdown 空間。
- **Focus:** 2px theme accent border，Light／Dark 都必須可見。
- **Error / Disabled:** error 使用 error semantic tone；disabled 使用現行 disabled surface、quiet text 與相同幾何。

### Provider Status Rows
Translation card 內以小型 status frames 呈現 Local Gemma、Online Gemma、Luna；每列依序放 provider name、status、detail 與 scope。Online Gemma 內縮放置兩個模型列，並保持同一把 API key 的語意；狀態文字必須與 UI 狀態一致，不把模型列畫成獨立導航或 dispatch board。這些內容只在 Translation card-local scroll 內流動。

### Provider Disclosure & Secret-Safe Rows
Local Gemma、Online Gemma 與 Luna 是互不排斥的三個 provider disclosure；各自預設收合，使用原生 disclosure arrow，不用自繪 glyph。Header 必須顯示 provider name＋status，下一行允許 capability wrapping；真正設定只放在 body，不把設定值塞進摘要。

收合狀態只屬於當次 UI session，不持久化；header 可用 Space／Enter 切換。收合時 body 內的焦點必須回到 header，provider status refresh 不得自行展開或改寫使用者的收合選擇。

任何 secret（包含 API key 值）不得出現在 provider 摘要、accessible name／description、截圖或 metadata。API key row 使用可伸展的 input，Show／Hide control 至少 60px 寬；輸入與控制不可裁切，也不可造成水平 overflow。

透明 provider surface 只使用 1px theme-aware border、top highlight 與 2px bottom tonal edge 建立克制立體感；禁止 gradient、glow 與 heavy shadow。Nested model row 只借用 provider surface 的分層，不再套第二個完整 frame。Provider name 固定 13px bold；status／detail／capability 約 10–11px。Metadata 必須使用對比 token：Light `provider-metadata-light=#636366`、Dark `provider-metadata-dark=#E5E5EA`、High Contrast `provider-metadata-high-contrast=#FFFFFF`。

### Header Band
Header 是固定在背景前方、跨越整個 settings surface 寬度的 opaque band。Light 使用 `settings_top_bg=#F2F2F7`，Dark 使用 `settings_top_bg=#1C1C1E`；品牌、主題／語言控制、工作控制與 Close 不可被角色背景沖淡。

### Fixed Footer
Footer 固定在 Settings body 底部並跨越整個 surface 寬度，放 Reset defaults、Cancel 與 Save；Save 是唯一 primary action，其餘是次要 input-surface controls。Translation 內部 scroll 不得帶走 footer。

## Do's and Don'ts

### Do:
- **Do** 以 Git 舊版三欄結構呈現 Translation／OCR／Rendering+Relief，維持近等寬、每欄至少 300px 與 14px grid gap。
- **Do** 讓透明 body host 左對齊，cluster 維持 928–1040px 寬，並在右側保留至少約 280px 角色 safe area（1422px capture 約 419px）。
- **Do** 保留全幅 `assets/bg_light.jpg`／`assets/bg_dark.jpg` 角色背景，讓它只作 light／dark ambient backdrop。
- **Do** 讓 header 使用現行 opaque `settings_top_bg`（Light `#F2F2F7`、Dark `#1C1C1E`），footer 保持固定且在前景。
- **Do** 讓 Translation card 只在自身內容過長時垂直 scroll，容納 Online Gemma 單 key 雙模型與 Luna。
- **Do** 將 Local Gemma、Online Gemma、Luna 視為可獨立展開的 disclosure；摘要只放 provider name、status 與可換行 capability，設定留在 body。
- **Do** 保持 disclosure 收合為 UI session 狀態，支援 Space／Enter，收合後把焦點送回 header，refresh 不自動展開。
- **Do** 讓 API key input 可伸展，Show／Hide 至少 60px，並在長值與窄寬下避免裁切／水平 overflow；摘要、accessible name／description、截圖與 metadata 一律不含 secret。
- **Do** 用 1px border＋top highlight＋2px bottom tonal edge 表達 provider surface，並讓 nested model row 避免 double-frame。
- **Do** 使用原生 Qt controls、清楚文字、可見 focus 與文字／形狀／色彩三重狀態提示。
- **Do** 在 high contrast 或背景圖不可用時回到 fallback surface，不讓插畫污染操作層。

### Don't:
- **Don't** 把 shipping UI 改回 left-nav、illustration rail、dispatch board 或全頁 single-column 工作面。
- **Don't** 將 Translation／OCR／Rendering+Relief 合併成不等寬的卡片牆，或讓 Translation 的 provider 內容推走固定 footer。
- **Don't** 讓角色背景覆蓋 header、footer、API key、文字、controls 或 Translation scroll。
- **Don't** 使用新版 navy dispatch palette、漸層、霓虹 glow、厚重玻璃或每卡 block shadow。
- **Don't** 把 Online Gemma 兩個模型當成兩把 key、兩個 provider 或額外 quota；只呈現實際可得的 status／rate／cooldown 資訊。
- **Don't** 把 provider body 設定塞進摘要、accessible name／description、截圖或 metadata，也不要因 status refresh 自行展開 disclosure。
- **Don't** 用 gradient、glow、heavy shadow 或 nested double-frame 製造 provider surface 的層次。
- **Don't** 用 emoji glyph、bitmap 字或 icon font 取代文字與現有 code-native marks。
