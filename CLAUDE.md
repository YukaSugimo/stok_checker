# 株価チェッカー プロジェクト

## プロジェクト概要

Yahoo Financeから指定銘柄の株価データを取得し、移動平均をもとに買いシグナルを判定して Discord に通知する自動ツール。Windowsタスクスケジューラで定時実行する。

- **開発目的**: Claude Codeを使いこなす経験を積む
- **最終ゴール**: 買いシグナルを毎日自動でDiscordに通知する
- **現在のフェーズ**: Phase 1（株価データ取得・CSV出力）

---

## 絶対にやってはいけないこと

- 実際の証券会社APIへの発注処理を実装しない
- `.env` ファイルをGitにコミットしない
- Webhook URLをコードに直接書かない
- パラメータをコードにハードコードしない（必ずconfig/に切り出す）

---

## ファイル構成

```
stock-checker/
├── CLAUDE.md               # このファイル
├── main.py                 # エントリーポイント（タスクスケジューラから実行）
├── config/
│   ├── symbols.py          # 銘柄コードリスト（変更頻度：高）
│   ├── params.py           # 分析パラメータ（変更頻度：中）
│   └── paths.py            # パス設定（変更頻度：低）
├── fetcher.py              # データ取得・CSV保存（Phase 1）
├── analyzer.py             # CSV読込・シグナル判定・CSV保存（Phase 2）
├── notifier.py             # Discord通知（Phase 2）
├── .env                    # 秘密情報（Gitに含めない）
├── .gitignore              # Git管理対象外の定義
├── output/                 # CSV出力先（自動生成・Gitに含めない）
└── logs/                   # ログ出力先（自動生成・Gitに含めない）
```

---

## 設定ファイルの役割

| ファイル | 管理する値 | 変更するタイミング |
|---|---|---|
| `config/symbols.py` | SYMBOLS（銘柄リスト） | 銘柄を追加・変更するとき |
| `config/params.py` | FETCH_DAYS / MA_DAYS / BUY_THRESHOLD | ロジック調整時 |
| `config/paths.py` | OUTPUT_DIR / LOG_DIR | フォルダ構成を変えるとき |
| `.env` | DISCORD_WEBHOOK_URL | Discord設定変更時 |

※ 実行時刻はコードでは管理しない。Windowsタスクスケジューラ側で直接設定する。

---

## コーディングルール

- コメントは必ず日本語で書く
- 関数には必ずdocstringを付ける（日本語で）
- エラーはすべてlogsに記録してスキップし、処理を継続する
- 実発注処理は絶対に書かない
- パラメータはconfig/に切り出し、コードにハードコードしない

---

## 各モジュールの責務

### main.py
全体の処理を順番に呼び出すだけ。ロジックもループも書かない。

```
①設定読込
②fetch_all(SYMBOLS, FETCH_DAYS)       # fetcher.py内でループ・取得・CSV保存
③analyze_all(fetch_results)           # analyzer.py内でループ・CSV読込・判定・CSV保存
④send_discord(signal_results)         # Discord通知
⑤ログ記録
```

### データの受け渡し
```
fetch_all()   →  [{symbol, path}, ...]        →  analyze_all()
analyze_all() →  [{symbol, signal, ...}, ...]  →  send_discord()
```

### fetcher.py
- `fetch_all(symbols, days)` → [{symbol, path}, ...]（全銘柄ループはここで管理）
- `fetch_stock(symbol, days)` → DataFrame（失敗時はNone）
- `save_csv(df, symbol)` → 保存パス

### analyzer.py（Phase 2）
- `analyze_all(fetch_results)` → [{symbol, signal, ...}, ...]（全銘柄ループはここで管理）
- `load_csv(file_path)` → DataFrame（失敗時はNone）
- `calc_moving_avg(df, days)` → DataFrame（ma列追加）
- `judge_signal(df, threshold)` → dict
- `save_signal_csv(results)` → 保存パス

### notifier.py（Phase 2）
- `send_discord(results)` → None

---

## CSV出力フォーマット

### stock_YYYYMMDD_銘柄コード.csv
```
date, open, high, low, close, volume, symbol
```

### signal_YYYYMMDD.csv
```
symbol, signal, close, ma, diff_pct, reason
```

---

## ログ管理

- 出力先: `logs/app_YYYYMMDD.log`
- 保持期間: 30日（main.py起動時に30日以前のログを自動削除）

---

## フェーズ管理

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1 | 株価データ取得・CSV出力 | 🔧 実装中 |
| Phase 2 | シグナル判定・Discord通知・定時実行 | ⏳ 未着手 |
| Phase 3 | 自動発注連携 | 🚫 スコープ外 |
| Phase 4 | 高度化（決算資料・スコアリング） | 💭 将来構想 |

---

## 使用ライブラリ

```
pip install yfinance pandas requests python-dotenv
```

---

## 参照ドキュメント

ドキュメントは `doc/` フォルダ以下に格納されている。

```
doc/
├── 1.要件定義/
│   └── 要件定義書_株価チェッカー.xlsx         # v3
└── 2.基本設計/
    ├── 基本設計_システム構成.xlsx              # v2
    ├── 基本設計_ファイル構成.xlsx              # v3
    ├── 基本設計_ファイル役割.xlsx              # v4
    └── 基本設計_関数設計.xlsx                  # v4
```
