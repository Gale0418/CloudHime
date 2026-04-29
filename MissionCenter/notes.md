# Notes

- 參考圖來自 image2 生成的 CloudHime 設定面板 mockup。
- 實作時以「接近一模一樣」為目標，但需服從現有 PySide6 控制項與功能限制。
- 保留現有 widget 屬性名稱，避免外部 controller 同步壞掉。
- OCR backend panel 原本在 header，這次要移進 OCR 欄，讓 header 更像 mockup。
- 需要真正 smoke test，不能只靠目測或口頭宣稱。
