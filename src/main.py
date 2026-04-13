# 株価チェッカー エントリーポイント
# タスクスケジューラから直接実行される
# このファイルはモジュール呼び出しのみ行う。ロジックもループも書かない。
# 処理順序: ①設定読込 → ②fetch_all() → ③analyze_all()[Phase2] → ④send_discord()[Phase2] → ⑤ログ記録

import logging
import os
import sys
from datetime import datetime, timedelta

# src/ ディレクトリをモジュール検索パスに追加する（タスクスケジューラから実行される場合にも対応）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.params import FETCH_DAYS, MA_DAYS, BUY_THRESHOLD
from config.paths import LOG_DIR, OUTPUT_DIR
from config.symbols import SYMBOLS
from fetcher import fetch_all


# ========================================
# ロガーの初期化
# ========================================

def _setup_logger() -> logging.Logger:
    """
    ロガーを初期化する。

    ログ出力先フォルダを自動生成し、今日の日付でログファイルを作成する。
    コンソールとファイルの両方にログを出力する。

    Returns:
        logging.Logger: 設定済みのロガーオブジェクト
    """
    # ログ出力先フォルダが存在しない場合は自動生成する
    os.makedirs(LOG_DIR, exist_ok=True)

    # ログファイル名を組み立てる
    today_str = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOG_DIR, f"app_{today_str}.log")

    # ロガーを設定する
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # フォーマットを定義する
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ファイルハンドラを追加する（追記モード、UTF-8）
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # コンソールハンドラを追加する
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def _cleanup_old_logs(logger: logging.Logger) -> None:
    """
    30日以前のログファイルを自動削除する。

    main.py 起動時に実行し、logs/ フォルダ内の古いログを削除する。
    削除に失敗した場合はログに記録してスキップする。

    Args:
        logger (logging.Logger): ログ出力に使用するロガー
    """
    cutoff_date = datetime.now() - timedelta(days=30)
    logger.info(f"30日以前のログファイルを削除します（基準日: {cutoff_date.strftime('%Y-%m-%d')}）")

    try:
        for filename in os.listdir(LOG_DIR):
            # app_YYYYMMDD.log 形式のファイルだけを対象にする
            if not filename.startswith("app_") or not filename.endswith(".log"):
                continue

            file_path = os.path.join(LOG_DIR, filename)
            try:
                # ファイル名から日付を取り出す（app_YYYYMMDD.log → YYYYMMDD）
                date_str = filename[4:12]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                if file_date < cutoff_date:
                    os.remove(file_path)
                    logger.info(f"古いログファイルを削除しました: {filename}")
            except ValueError:
                # 日付パースに失敗したファイルはスキップする
                logger.warning(f"ログファイルの日付を解析できませんでした: {filename}")
                continue
            except Exception as e:
                logger.error(f"ログファイルの削除中にエラーが発生しました [{filename}]: {e}")
                continue

    except Exception as e:
        logger.error(f"ログフォルダの読み込み中にエラーが発生しました: {e}")


# ========================================
# Phase 2 スタブ関数（未実装）
# ========================================

def _analyze_all_stub(fetch_results: list) -> list:
    """
    シグナル判定処理のスタブ関数（Phase 2で実装予定）。

    Phase 2 実装時には analyzer.analyze_all() に置き換える。

    Args:
        fetch_results (list): fetch_all() の戻り値

    Returns:
        list: 空リスト（Phase 2 実装前のスタブ）
    """
    logger = logging.getLogger(__name__)
    logger.info("analyze_all() は Phase 2 で実装予定です。スキップします。")
    return []


def _send_discord_stub(signal_results: list) -> None:
    """
    Discord通知処理のスタブ関数（Phase 2で実装予定）。

    Phase 2 実装時には notifier.send_discord() に置き換える。

    Args:
        signal_results (list): analyze_all() の戻り値
    """
    logger = logging.getLogger(__name__)
    logger.info("send_discord() は Phase 2 で実装予定です。スキップします。")


# ========================================
# メイン処理
# ========================================

def main() -> None:
    """
    ツール全体の処理を順番に実行するエントリーポイント。

    処理順序:
        ① 設定読込・ロガー初期化
        ② fetch_all() で全銘柄の株価データを取得してCSVに保存する
        ③ analyze_all() でCSV読込・シグナル判定・結果CSV保存（Phase 2）
        ④ send_discord() でDiscordに通知する（Phase 2）
        ⑤ 処理完了をログに記録する
    """
    # ① 設定読込・ロガー初期化
    logger = _setup_logger()
    logger.info("=" * 60)
    logger.info("株価チェッカーを起動しました。")
    logger.info(f"  対象銘柄数: {len(SYMBOLS)}")
    logger.info(f"  取得日数  : {FETCH_DAYS} 日")
    logger.info(f"  移動平均  : {MA_DAYS} 日")
    logger.info(f"  買い閾値  : {BUY_THRESHOLD * 100:.1f} %")

    # 30日以前の古いログファイルを自動削除する
    _cleanup_old_logs(logger)

    # CSV出力先フォルダが存在しない場合は自動生成する
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ② 全銘柄の株価データを取得してCSVに保存する
    fetch_results = []
    try:
        fetch_results = fetch_all(SYMBOLS, FETCH_DAYS)
        logger.info(f"fetch_all() 完了: {len(fetch_results)} 銘柄のデータを取得・保存しました。")
    except Exception as e:
        logger.error(f"fetch_all() で予期しないエラーが発生しました: {e}", exc_info=True)

    # ③ シグナル判定・結果CSV保存（Phase 2 で実装予定）
    signal_results = []
    try:
        signal_results = _analyze_all_stub(fetch_results)
    except Exception as e:
        logger.error(f"analyze_all() で予期しないエラーが発生しました: {e}", exc_info=True)

    # ④ Discord通知（Phase 2 で実装予定）
    try:
        _send_discord_stub(signal_results)
    except Exception as e:
        logger.error(f"send_discord() で予期しないエラーが発生しました: {e}", exc_info=True)

    # ⑤ 処理完了をログに記録する
    logger.info("株価チェッカーの処理が完了しました。")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
