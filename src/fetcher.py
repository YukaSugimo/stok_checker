# Yahoo Financeから株価データを取得し、CSVに保存するモジュール
# fetch_all() が全銘柄のループを管理し、内部で fetch_stock() → save_csv() を呼び出す
# エラーが発生した銘柄はスキップしてログに記録し、残りの銘柄の処理を継続する

import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from config.paths import OUTPUT_DIR


def fetch_all(symbols: list, days: int) -> list:
    """
    全銘柄のデータ取得・CSV保存をまとめて実行する。

    全銘柄をループして fetch_stock() でデータを取得し、
    取得に成功した銘柄は save_csv() でCSVに保存する。
    取得・保存に失敗した銘柄はスキップしてログに記録し、処理を継続する。

    Args:
        symbols (list): 銘柄コードのリスト（例: ['7203.T', '6758.T']）
        days (int): 取得する日数

    Returns:
        list[dict]: 取得・保存に成功した銘柄の情報リスト
            [
                {'symbol': str, 'path': str},
                ...
            ]
            取得失敗銘柄は除外される
    """
    logger = logging.getLogger(__name__)
    results = []

    logger.info(f"全銘柄の取得処理を開始します。対象銘柄数: {len(symbols)}")

    for symbol in symbols:
        try:
            # 株価データを取得する
            df = fetch_stock(symbol, days)
            if df is None:
                # fetch_stock() 内でエラーログ記録済み
                logger.warning(f"[{symbol}] データ取得に失敗したためスキップします。")
                continue

            # CSVに保存する
            saved_path = save_csv(df, symbol)
            if saved_path is None:
                # save_csv() 内でエラーログ記録済み
                logger.warning(f"[{symbol}] CSV保存に失敗したためスキップします。")
                continue

            results.append({"symbol": symbol, "path": saved_path})
            logger.info(f"[{symbol}] 取得・保存完了: {saved_path}")

        except Exception as e:
            # 想定外のエラーが発生してもスキップして継続する
            logger.error(f"[{symbol}] 予期しないエラーが発生しました: {e}", exc_info=True)
            continue

    logger.info(f"全銘柄の取得処理が完了しました。成功: {len(results)}/{len(symbols)} 銘柄")
    return results


def fetch_stock(symbol: str, days: int) -> pd.DataFrame:
    """
    指定銘柄の株価データをYahoo Financeから取得する。

    yfinanceライブラリを使用して、指定した日数分の株価データを取得する。
    取得したDataFrameには date, open, high, low, close, volume, symbol 列を含む。
    取得に失敗した場合は None を返す。

    Args:
        symbol (str): 銘柄コード（例: '7203.T'）
        days (int): 取得する日数

    Returns:
        pd.DataFrame: 取得した株価データ（取得成功時）
        None: 取得失敗時
    """
    logger = logging.getLogger(__name__)

    try:
        # 取得期間を計算する（今日から days 日前まで）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.debug(
            f"[{symbol}] 株価データを取得します。期間: {start_date.strftime('%Y-%m-%d')} ～ {end_date.strftime('%Y-%m-%d')}"
        )

        # yfinanceでデータを取得する
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )

        # データが空の場合はエラーとして扱う
        if df is None or df.empty:
            logger.error(f"[{symbol}] 取得したデータが空です。銘柄コードが正しいか確認してください。")
            return None

        # カラム名を小文字に統一する
        df.columns = [col.lower() for col in df.columns]

        # インデックス（日付）をリセットして date 列にする
        df = df.reset_index()
        df = df.rename(columns={"index": "date", "Date": "date"})

        # date 列をYYYY-MM-DD形式の文字列に変換する
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # 必要な列だけを抽出し、symbol 列を追加する
        required_columns = ["date", "open", "high", "low", "close", "volume"]
        df = df[required_columns].copy()
        df["symbol"] = symbol

        logger.debug(f"[{symbol}] {len(df)} 件のデータを取得しました。")
        return df

    except Exception as e:
        logger.error(f"[{symbol}] データ取得中にエラーが発生しました: {e}", exc_info=True)
        return None


def save_csv(df: pd.DataFrame, symbol: str) -> str:
    """
    取得した株価データをCSVファイルに保存する。

    ファイル名は stock_YYYYMMDD_銘柄コード.csv 形式とする。
    出力先フォルダが存在しない場合は自動生成する。
    保存に失敗した場合は None を返す。

    Args:
        df (pd.DataFrame): 保存する株価データ
        symbol (str): 銘柄コード（例: '7203.T'）

    Returns:
        str: 保存したファイルパス（保存成功時）
        None: 保存失敗時
    """
    logger = logging.getLogger(__name__)

    try:
        # 出力先フォルダが存在しない場合は自動生成する
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ファイル名を組み立てる（銘柄コードの "." をアンダースコアに変換しない：仕様通り使用）
        today_str = datetime.now().strftime("%Y%m%d")
        filename = f"stock_{today_str}_{symbol}.csv"
        file_path = os.path.join(OUTPUT_DIR, filename)

        # CSVとして保存する（インデックスなし、列順序は設計書に準拠）
        columns_order = ["date", "open", "high", "low", "close", "volume", "symbol"]
        df[columns_order].to_csv(file_path, index=False, encoding="utf-8-sig")

        logger.debug(f"[{symbol}] CSVを保存しました: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"[{symbol}] CSV保存中にエラーが発生しました: {e}", exc_info=True)
        return None
