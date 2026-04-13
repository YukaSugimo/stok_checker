# シグナル判定結果をDiscordに通知するモジュール
# .envファイルからDISCORD_WEBHOOK_URLを読み込み、HTTPリクエストでDiscordに送信する
# エラーが発生した場合はログに記録してスキップし、処理を継続する（クラッシュしない）

import logging
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from config.params import DISCORD_RETRY_COUNT, DISCORD_TIMEOUT_SEC

# .envファイルを読み込む（プロジェクトルートの.envを対象とする）
load_dotenv()


def send_discord(results: list) -> None:
    """
    シグナル判定結果をDiscord Webhookに送信する。

    DISCORD_WEBHOOK_URLは .envファイルから読み込む。
    送信に失敗した場合は DISCORD_RETRY_COUNT 回まで再試行する。
    すべてのリトライが失敗した場合はログに記録して処理を終了する（クラッシュしない）。
    シグナルがない場合は「本日のシグナルなし」メッセージを送信する。

    Args:
        results (list): analyze_all() が返すシグナル判定結果のリスト
            [{'symbol': str, 'signal': bool, 'close': float,
              'ma': float, 'diff_pct': float, 'reason': str}, ...]

    Returns:
        None
    """
    logger = logging.getLogger(__name__)

    # .envからDiscord Webhook URLを取得する
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # Webhook URLが設定されていない場合はエラーログを記録して終了する
    if not webhook_url:
        logger.error(
            "DISCORD_WEBHOOK_URL が設定されていません。"
            ".env ファイルに DISCORD_WEBHOOK_URL を設定してください。"
        )
        return

    # 送信するメッセージを組み立てる
    message = _build_message(results)

    # Discordへ送信する（失敗時はリトライする）
    _send_with_retry(webhook_url, message, logger)


def _build_message(results: list) -> str:
    """
    シグナル判定結果をDiscordに送信するメッセージ文字列を組み立てる。

    シグナルありの銘柄がある場合はその一覧を、
    ない場合は「本日のシグナルなし」メッセージを返す。

    Args:
        results (list): シグナル判定結果のリスト

    Returns:
        str: Discordに送信するメッセージ文字列
    """
    # シグナルあり銘柄を抽出する
    buy_signals = [r for r in results if r.get("signal") is True]

    # 送信日時を取得する
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not results or not buy_signals:
        # シグナルなし（対象銘柄が0件または全銘柄シグナルなし）
        return f"【株価チェッカー】{now_str}\n本日の買いシグナルはありませんでした。"

    # シグナルあり銘柄の一覧を組み立てる
    lines = [f"【株価チェッカー】{now_str}"]
    lines.append(f"買いシグナルあり: {len(buy_signals)} 銘柄")
    lines.append("")

    for r in buy_signals:
        symbol = r.get("symbol", "不明")
        close = r.get("close")
        ma = r.get("ma")
        diff_pct = r.get("diff_pct")
        reason = r.get("reason", "")

        # 数値の表示フォーマットを整える
        close_str = f"{close:.2f}" if close is not None else "N/A"
        ma_str = f"{ma:.2f}" if ma is not None else "N/A"
        diff_str = f"{diff_pct:.2f}%" if diff_pct is not None else "N/A"

        lines.append(f"銘柄: {symbol}")
        lines.append(f"  終値: {close_str}  移動平均: {ma_str}  乖離率: {diff_str}")
        lines.append(f"  {reason}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _send_with_retry(webhook_url: str, message: str, logger: logging.Logger) -> None:
    """
    指定したメッセージをDiscord WebhookへHTTP POSTで送信する。

    失敗した場合は DISCORD_RETRY_COUNT 回まで再試行する。
    すべてのリトライが失敗した場合はログに記録して処理を終了する（クラッシュしない）。

    Args:
        webhook_url (str): Discord Webhook URL
        message (str): 送信するメッセージ文字列
        logger (logging.Logger): ログ出力に使用するロガー

    Returns:
        None
    """
    payload = {"content": message}

    for attempt in range(1, DISCORD_RETRY_COUNT + 1):
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=DISCORD_TIMEOUT_SEC,
            )

            # Discord Webhookは成功時に 204 No Content を返す
            if response.status_code in (200, 204):
                logger.info(f"Discord通知を送信しました（試行: {attempt}/{DISCORD_RETRY_COUNT}）")
                return

            # HTTPエラーの場合はログに記録してリトライする
            logger.warning(
                f"Discord通知に失敗しました（試行: {attempt}/{DISCORD_RETRY_COUNT}）: "
                f"HTTP {response.status_code} - {response.text}"
            )

        except requests.exceptions.Timeout:
            logger.warning(
                f"Discord通知がタイムアウトしました（試行: {attempt}/{DISCORD_RETRY_COUNT}）: "
                f"タイムアウト秒数={DISCORD_TIMEOUT_SEC}秒"
            )
        except requests.exceptions.ConnectionError as e:
            logger.warning(
                f"Discord通知の接続に失敗しました（試行: {attempt}/{DISCORD_RETRY_COUNT}）: {e}"
            )
        except Exception as e:
            logger.warning(
                f"Discord通知中に予期しないエラーが発生しました（試行: {attempt}/{DISCORD_RETRY_COUNT}）: {e}",
                exc_info=True,
            )

        # 最終リトライでなければ少し待機してから再試行する
        if attempt < DISCORD_RETRY_COUNT:
            time.sleep(2)

    # すべてのリトライが失敗した場合はエラーログを記録して処理を終了する
    logger.error(
        f"Discord通知がすべてのリトライで失敗しました（{DISCORD_RETRY_COUNT} 回試行）。"
        "Webhook URLと接続環境を確認してください。"
    )
