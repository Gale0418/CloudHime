# Native 元件告知

這些元件使用各自的授權，與 CloudHime 的 Apache 2.0 分開適用。

- NVIDIA `cublas64_12.dll`／`cublasLt64_12.dll` 對應 cuBLAS 12.4.5.8；`cudart64_12.dll` 對應 CUDA Runtime 12.4.127。三份 DLL 的 SHA-256 已與 NVIDIA 官方、整份壓縮檔 SHA-256 驗證通過的 Windows redistributable 比對一致。原始 EULA 位於 `cuda-12.4.5.8/LICENSE` 與 `cuda-12.4.127/LICENSE`，精確來源與 DLL 雜湊位於 `cuda-runtime-sources.json`。NVIDIA 保留其著作權；這些 DLL 不是以 Apache 2.0 再授權的元件。
- llama.cpp build 9968／commit `1d1d9a9ed` 使用 MIT，原文位於 `llama-1d1d9a9ed/LICENSE`。建置版本回報 Clang 20.1.8；LLVM／OpenMP 的來源授權原文位於 `llvm-20.1.8/`，此來源版本資訊不單獨構成 `libomp140.x86_64.dll` 的可重現建置證明。
- CPython 3.10.11 的完整授權與歷史告知位於 `cpython-3.10.11/LICENSE`。
- Qt 6.10 的 Windows 軟體 OpenGL 元件 `opengl32sw.dll` 使用 Mesa llvmpipe；Qt 官方該版告知中列出的 Mesa／Khronos／Boost 及 LLVM 告知保存在 `qt-6.10.1/LLVMPipe-LICENSE.txt`、`qt-6.10.1/LLVM-MESA-LICENSE.txt`。這個 LLVM 告知與 llama.cpp 使用的 Clang／OpenMP 是分開的來源。
- primp 1.3.1 的 Windows normal dependency tree 已盤點 203 個 crate／workspace 元件，逐一保存來源中的授權／告知於 `primp-native-notices/`，包括 AWS-LC、rustls、zlib-rs、zstd、hickory、PyO3 等。registry crate 原始壓縮檔經 Cargo.lock SHA-256 驗證；兩個缺 crate-local 授權檔的元件另從對應 workspace parent 補齊。清單位於 `primp-native-notice-manifest.json`。這份清單是 normal dependency tree 的來源告知覆蓋，未冒稱已取得 wheel 的完整建置 attestation，亦不包含所有 build-only dependency。
- OpenCV、NumPy／OpenBLAS、lxml／libxml2／libxslt、PyWinRT 等生產 wheel 的原始告知保存於套件的 `_internal/dependency-licenses/packages/`；請同時閱讀各 wheel 的 LICENSE、NOTICE 與第三方告知。來源副本不能代替該元件自身的授權。

`sources.json` 記錄以上保存檔案的來源 URL、bytes 與 SHA-256。Qt 與 primp 的來源告知集合刻意包含來源中的告知超集合；其中出現某份授權，不代表每個源碼元件都編入 CloudHime。最終上架仍須核對 Qt 原始碼供應、修改函式庫執行途徑與 Microsoft Store 實際條款，以及發行驗證結果。
