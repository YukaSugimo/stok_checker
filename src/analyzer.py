# CSVから株価データを読み込み、移動平均をもとに買いシグナルを判定してCSVに保存するモジュール
# analyze_all() が全銘柄のループを管理し、内部で load_csv() → calc_moving_avg() → judge_signal() を呼び出す
# エラーが発生した銘柄はスキップしてログに記録し、残りの銘柄の処理を継続する

import logging
import math
import os
from datetime import datetime

import pandas as pd

from config.params import BUY_THRESHOLD, MA_DAYS
from config.paths import OUTPUT_DIR


def analyze_all(fetch_results: list) -> list:
    """
    全銘柄のシグナル判定・CSV保存をまとめて実行する。

    全銘柄をループして load_csv() でCSVを読み込み、
    calc_moving_avg() で移動平均を計算し、
    judge_signal() でシグナルを判定する。
    最後に save_signal_csv() で結果をCSVに保存する。
    失敗した銘柄はスキップしてログに記録し、処理を継続する。

    Args:
        fetch_results (list): fetch_all() の返り値。銘柄ごとの dict のリスト。
            [{'symbol': str, 'path': str}, ...]

    Returns:
        list[dict]: シグナル判定結果のリスト
            [{'symbol': str, 'signal': bool, 'close': float,
              'ma': float, 'diff_pct': float, 'reason': str}, ...]
            失敗銘柄は除外される
    """
    logger = logging.getLogger(__name__)
    results = []

    logger.info(f"全銘柄のシグナル判定処理を開始します。対象銘柄数: {len(fetch_results)}")

    for item in fetch_results:
        symbol = item.get("symbol", "不明")
        file_path = item.get("path")

        try:
            # CSVを読み込む
            df = load_csv(file_path)
            if df is None:
                logger.warning(f"[{symbol}] CSV読み込みに失敗したためスキップします。")
                continue

            # 移動平均を計算する
            df = calc_moving_avg(df, MA_DAYS)

            # シグナルを判定する
            signal_dict = judge_signal(df, BUY_THRESHOLD)

            # symbolキーが存在しない場合はfetch_resultsの値で補完する
            if "symbol" not in signal_dict or not signal_dict["symbol"]:
                signal_dict["symbol"] = symbol

            results.append(signal_dict)
            logger.info(
                f"[{symbol}] シグナル判定完了: signal={signal_dict['signal']}, "
                f"close={signal_dict['close']}, ma={signal_dict['ma']}, "
                f"diff_pct={signal_dict['diff_pct']}"
            )

        except Exception as e:
            # 想定外のエラーが発生してもスキップして継続する
            logger.error(f"[{symbol}] 予期しないエラーが発生しました: {e}", exc_info=True)
            continue

    # シグナル結果をCSVに保存する
    if results:
        save_path = save_signal_csv(results)
        if save_path:
            logger.info(f"シグナルCSVを保存しました: {save_path}")
        else:
            logger.warning("シグナルCSVの保存に失敗しました。")

    logger.info(
        f"全銘柄のシグナル判定処理が完了しました。"
        f"成功: {len(results)}/{len(fetch_results)} 銘柄"
    )
    return results


def load_csv(file_path: str) -> pd.DataFrame:
    """
    fetcher.py の save_csv() が保存したCSVファイルを読み込む。

    エンコーディングは utf-8-sig（BOM付きUTF-8）を使用する。
    utf-8 を使用した場合、先頭列名が '\\ufeffdate' になり列選択が失敗するため注意。
    ファイルが存在しない場合やパースに失敗した場合は None を返す。

    Args:
        file_path (str): 読み込むCSVファイルのパス

    Returns:
        pd.DataFrame: 読み込んだ株価データ（成功時）
        None: 失敗時
    """
    logger = logging.getLogger(__name__)

    # ファイルパスが None または空の場合はエラーとして扱う
    if not file_path:
        logger.error("ファイルパスが指定されていません。")
        return None

    try:
        # ファイルが存在するか確認する
        if not os.path.exists(file_path):
            logger.error(f"CSVファイルが存在しません: {file_path}")
            return None

        # BOM付きUTF-8で読み込む（fetcher.py の save_csv() に合わせる）
        df = pd.read_csv(file_path, encoding="utf-8-sig")

        # データが空の場合はエラーとして扱う
        if df.empty:
            logger.error(f"CSVファイルが空です: {file_path}")
            return None

        logger.debug(f"CSVを読み込みました: {file_path} ({len(df)} 件)")
        return df

    except Exception as e:
        logger.error(f"CSV読み込み中にエラーが発生しました [{file_path}]: {e}", exc_info=True)
        return None


def calc_moving_avg(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """
    close列の単純移動平均を計算し、ma列としてDataFrameに追加する。

    pandas の rolling().mean() を使用して指定日数の移動平均を計算する。
    データ件数が days 未満の場合、先頭の行は NaN になる。

    Args:
        df (pd.DataFrame): 株価データ（close列が必須）
        days (int): 移動平均の計算日数

    Returns:
        pd.DataFrame: ma列を追加したDataFrame
    """
    logger = logging.getLogger(__name__)

    # close列の存在確認
    if "close" not in df.columns:
        logger.error(f"close列が存在しません。実際の列: {list(df.columns)}")
        # ma列をNaNで追加して返す（後続処理でNaN判定できるようにする）
        df["ma"] = float("nan")
        return df

    # 単純移動平均を計算してma列に格納する
    df = df.copy()
    df["ma"] = df["close"].rolling(window=days).mean()

    logger.debug(f"移動平均を計算しました（{days}日）。有効データ数: {df['ma'].notna().sum()} 件")
    return df


def judge_signal(df: pd.DataFrame, threshold: float) -> dict:
    """
    直近終値が移動平均を threshold % 以上上回っている場合に買いシグナルと判定する。

    判定条件: 直近終値 > 移動平均 × (1 + threshold)
    移動平均が NaN の場合（データ不足）はシグナルなしとして扱う。

    Args:
        df (pd.DataFrame): ma列を含む株価データ
        threshold (float): 買いシグナル閾値（小数表記。例: 0.02 = 2%）

    Returns:
        dict: シグナル判定結果
            {
                'symbol': str,      # 銘柄コード（CSVのsymbol列から取得）
                'signal': bool,     # シグナルあり: True / なし: False
                'close': float,     # 直近終値
                'ma': float,        # 直近移動平均（NaNの場合は None）
                'diff_pct': float,  # 終値と移動平均の乖離率（%）
                'reason': str,      # 判定理由
            }
    """
    logger = logging.getLogger(__name__)

    # 直近行（最終行）のデータを取得する
    latest = df.iloc[-1]

    # symbolの取得（symbol列が存在しない場合は空文字）
    symbol = str(latest.get("symbol", "")) if "symbol" in df.columns else ""

    # 直近終値を取得する
    close = float(latest["close"]) if "close" in df.columns else float("nan")

    # 直近移動平均を取得する
    ma_raw = latest.get("ma", float("nan")) if "ma" in df.columns else float("nan")

    # 移動平均がNaNの場合（データ不足）はシグナルなしとして返す
    if ma_raw is None or (isinstance(ma_raw, float) and math.isnan(ma_raw)):
        logger.warning(f"[{symbol}] 移動平均がNaNです。データ件数が不足している可能性があります。")
        return {
            "symbol": symbol,
            "signal": False,
            "close": close,
            "ma": None,
            "diff_pct": None,
            "reason": "移動平均の計算に必要なデータが不足しています",
        }

    ma = float(ma_raw)

    # 乖離率を計算する（%表記）
    diff_pct = ((close - ma) / ma) * 100 if ma != 0 else 0.0

    # 買いシグナルを判定する
    signal = close > ma * (1 + threshold)

    if signal:
        reason = (
            f"終値({close:.2f})が移動平均({ma:.2f})を"
            f"{diff_pct:.2f}%上回っています（閾値: {threshold * 100:.1f}%）"
        )
    else:
        reason = (
            f"終値({close:.2f})が移動平均({ma:.2f})を"
            f"{diff_pct:.2f}%の乖離（閾値: {threshold * 100:.1f}%）"
        )

    logger.debug(f"[{symbol}] signal={signal}, close={close:.2f}, ma={ma:.2f}, diff_pct={diff_pct:.2f}%")

    return {
        "symbol": symbol,
        "signal": signal,
        "close": close,
        "ma": ma,
        "diff_pct": round(diff_pct, 4),
        "reason": reason,
    }


def save_signal_csv(results: list) -> str:
    """
    シグナル判定結果を signal_YYYYMMDD.csv に保存する。

    出力先フォルダが存在しない場合は自動生成する。
    保存に失敗した場合は None を返す。

    Args:
        results (list): analyze_all() が返すシグナル判定結果のリスト
            [{'symbol': str, 'signal': bool, 'close': float,
              'ma': float, 'diff_pct': float, 'reason': str}, ...]

    Returns:
        str: 保存したファイルパス（成功時）
        None: 失敗時
    """
    logger = logging.getLogger(__name__)

    try:
        # 出力先フォルダが存在しない場合は自動生成する
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ファイル名を組み立てる
        today_str = datetime.now().strftime("%Y%m%d")
        filename = f"signal_{today_str}.csv"
        file_path = os.path.join(OUTPUT_DIR, filename)

        # 同日分のCSVが既に存在する場合は警告する
        if os.path.exists(file_path):
            logger.warning(f"本日分のシグナルCSVが既に存在します。上書きします: {file_path}")

        # DataFrameに変換して保存する（設計書に準拠した列順序）
        columns_order = ["symbol", "signal", "close", "ma", "diff_pct", "reason"]
        df = pd.DataFrame(results, columns=columns_order)

        # CSVとして保存する（インデックスなし、BOM付きUTF-8でExcel互換性を確保）
        df.to_csv(file_path, index=False, encoding="utf-8-sig")

        logger.debug(f"シグナルCSVを保存しました: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"シグナルCSV保存中にエラーが発生しました: {e}", exc_info=True)
        return None
