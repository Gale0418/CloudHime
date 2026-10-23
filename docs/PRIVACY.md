# CloudHime Privacy Policy / 隱私權政策 / プライバシーポリシー

Effective date: 2026-09-23. Publisher: WindSheep. Privacy and support inquiries: [CloudHime support](https://github.com/Gale0418/CloudHime/issues). GitHub issues are public; do not post API keys, screenshots, or other private information there.

## 繁體中文

CloudHime 是 Windows 螢幕 OCR 與翻譯應用程式。本政策說明此版本在您使用掃描、翻譯和知識研究功能時如何處理資料。螢幕畫面與辨識文字可能含有您或他人的個人資料；請只處理您有權使用的內容。

**擷取與翻譯。** 當您啟動掃描或啟用自動掃描時，CloudHime 擷取全螢幕或選定區域。本機 OCR 與本機模型可在裝置上處理內容。選用 Google 翻譯時，待翻譯文字會送往 Google；選用 Google OCR、線上 Gemma 視覺翻譯或 OpenAI 視覺翻譯時，畫面影像及相關提示可能送往所選服務；其他線上文字翻譯會送出辨識文字與相關提示。您也可自行設定模型端點；若端點位於其他電腦，內容會送往該端點。第三方服務依各自的條款和隱私政策處理資料，CloudHime 無法承諾它們的保存或使用方式。

**API 金鑰。** 若使用雲端模型，您自行提供所需金鑰。CloudHime 將金鑰以 Windows DPAPI 的使用者範圍保護後存在本機，而非寫入一般設定 JSON；呼叫服務時，金鑰會送往對應供應者進行驗證。清空金鑰欄位並儲存可移除本機金鑰檔。手動檢查可用模型也會將相應金鑰送往供應者。

**知識研究。** 只有您啟動研究時，搜尋詞才會交由 DDGS 搜尋，選定或指定的公開網址會送往 Jina Reader 讀取，網頁文字與研究標題會送往您選用的 Google 或 OpenAI 模型以整理候選資料。您確認候選後，CloudHime 才將 Knowledge Pack、來源網址及擷取的頁面內容保存在本機。請勿以此功能輸入機密或未公開資料。

**本機資料及刪除。** 設定、掃描區域、自訂提示、加密的金鑰、翻譯快取、模型可用性快照、Knowledge Pack 及輪替日誌保存在 `%APPDATA%\CloudHime`。快取可能含翻譯文字；Knowledge Pack 可能含來源頁面文字；日誌可能含錯誤訊息或本機路徑。本機下載模型保存在 `%LOCALAPPDATA%\CloudHime\models`；完整離線套件亦可能隨安裝包提供模型。這些本機資料會保留到您刪除為止。要完整移除使用者資料，請先關閉 CloudHime，再刪除上述 AppData 資料夾；若要移除另行下載的模型，也刪除上述 models 資料夾。重新使用功能可能重建資料。

此版本 CloudHime 本身不提供帳號登入、廣告、第一方分析或自動上傳錯誤報告。這不涵蓋 Windows、Microsoft Store 或您選用的第三方服務之資料處理。隱私問題請透過上方支援頁聯繫，並避免在公開 issue 中張貼個人資料。

## English

CloudHime is a Windows screen OCR and translation app. This policy describes this version's handling of data when you use scanning, translation, and knowledge research. Screen images and recognized text may contain personal information about you or others. Process only content you are entitled to use.

**Capture and translation.** When you start a scan or enable automatic scanning, CloudHime captures the full screen or your selected area. Local OCR and local models can process content on your device. Google Translate receives text when selected. Google OCR, online Gemma vision translation, and OpenAI vision translation may receive images and related prompts when selected; other online text translation receives recognized text and related prompts. You can configure a model endpoint; if it points to another computer, content is sent there. Third-party providers process requests under their own terms and privacy policies. CloudHime cannot promise how they retain or use request data.

**API keys.** You provide the keys needed for cloud models. CloudHime protects keys locally with Windows user-scope DPAPI rather than writing them to the ordinary settings JSON. Requests send each key to its provider for authentication. Clearing a key field and saving removes its local key file. A manual model availability check also sends the relevant key to the provider.

**Knowledge research.** Only when you start research, a query is sent through DDGS search, selected or supplied public URLs are sent to Jina Reader, and retrieved page text and the research title are sent to your selected Google or OpenAI model to extract candidate entries. After you confirm a candidate, CloudHime saves a local Knowledge Pack including source URLs and retrieved page content. Do not enter confidential or unpublished information into this feature.

**Local data and deletion.** `%APPDATA%\CloudHime` stores settings, scan regions, custom prompts, protected keys, translation cache, model availability snapshots, Knowledge Packs, and rotating logs. The cache may contain translated text; Knowledge Packs may contain source page text; logs may contain errors or local paths. Downloaded local models are stored in `%LOCALAPPDATA%\CloudHime\models`; a full offline package may include models. Local data remains until you delete it. To remove user data, close CloudHime and delete the AppData folder above; delete the models folder too if you want to remove separately downloaded models. Using the features again may recreate data.

This version of CloudHime itself has no account sign-in, ads, first-party analytics, or automatic crash-report upload. That statement does not cover Windows, Microsoft Store, or third-party providers. Use the support link above for privacy inquiries, and avoid posting personal information in a public issue.

## 日本語

CloudHime は Windows 向けの画面 OCR・翻訳アプリです。この方針は、画面の読み取り、翻訳、資料調査の機能を利用する際の、このバージョンのデータの扱いを説明します。画面や認識した文字には、ご自身や第三者の個人情報が含まれる場合があります。利用する権利のある内容だけを処理してください。

**画面の取得と翻訳。** 手動で読み取りを開始するか自動読み取りを有効にすると、画面全体または選択範囲を取得します。ローカル OCR とローカルモデルは端末上で処理できます。Google 翻訳を選ぶと翻訳対象の文字が Google に送信されます。Google OCR、オンライン Gemma の画像翻訳、OpenAI の画像翻訳を選ぶと、画像と関連する指示がそのサービスに送信される場合があります。ほかのオンライン文字翻訳では認識した文字と関連する指示が送信されます。モデルの接続先を別のコンピューターに設定した場合、内容はその接続先に送信されます。外部サービスはそれぞれの規約とプライバシーポリシーに従ってデータを扱い、CloudHime はその保存・利用方法を保証できません。

**API キー。** クラウドモデルに必要なキーは利用者が用意します。CloudHime は通常の設定 JSON には書かず、Windows のユーザー単位の DPAPI で保護して端末に保存します。サービスへの要求時には、認証のため対応する提供元にキーを送信します。キーの入力欄を空にして保存すると、端末上のキーファイルを削除できます。モデルの利用可否を手動で確認する際も、対応するキーを提供元に送信します。

**資料調査。** 利用者が調査を開始した場合に限り、検索語を DDGS 検索に送り、指定・選択した公開 URL を Jina Reader に送り、取得したページの文章と調査名を選択した Google または OpenAI のモデルに送って候補を抽出します。候補を確認すると、出典 URL と取得したページ内容を含む Knowledge Pack を端末に保存します。秘密情報や未公開情報を入力しないでください。

**端末内のデータと削除。** `%APPDATA%\CloudHime` に設定、読み取り範囲、独自の指示、保護されたキー、翻訳キャッシュ、モデルの利用可否情報、Knowledge Pack、ローテーションするログを保存します。キャッシュには翻訳文、Knowledge Pack には出典ページの文章、ログにはエラーや端末内のパスが含まれる場合があります。別途ダウンロードしたローカルモデルは `%LOCALAPPDATA%\CloudHime\models` に保存され、完全オフライン版にはモデルが同梱される場合もあります。端末内のデータは利用者が削除するまで残ります。削除する際は CloudHime を終了し、上記の AppData フォルダーを削除してください。別途ダウンロードしたモデルも削除する場合は models フォルダーを削除してください。機能を再利用するとデータが再作成される場合があります。

このバージョンの CloudHime 自体には、アカウントへのログイン、広告、独自の分析機能、自動的なクラッシュレポート送信はありません。Windows、Microsoft Store、外部サービスによるデータ処理には適用されません。プライバシーに関するお問い合わせは上記のサポート先をご利用ください。公開 issue に個人情報を書き込まないでください。
