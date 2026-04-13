# パス・ディレクトリ設定を管理するファイル
# CSV出力先・ログ出力先のパスを管理する
# 環境が変わったときはここだけ修正すれば良い
# 注意: フォルダが存在しない場合は main.py 起動時に自動生成する

import os

# このファイル（paths.py）が置かれているディレクトリを基準に絶対パスを構築する
# src/config/paths.py → 3階層上がりプロジェクトルート（stock-checker/）を取得する
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CSV出力先フォルダのパス（自動生成・Gitに含めない）
OUTPUT_DIR = os.path.join(_BASE_DIR, "output")

# ログ出力先フォルダのパス（自動生成・Gitに含めない）
LOG_DIR = os.path.join(_BASE_DIR, "logs")
