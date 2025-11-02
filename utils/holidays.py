"""日本の祝日管理機能"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Optional
import pytz


class HolidayManager:
    """日本の祝日を管理するクラス"""
    
    def __init__(self, holidays_file: str = "data/holidays.json"):
        """
        Args:
            holidays_file: 祝日データファイルのパス
        """
        self.holidays_file = holidays_file
        self.jst = pytz.timezone("Asia/Tokyo")
        self._ensure_file_exists()
        self._load_holidays()
    
    def _ensure_file_exists(self):
        """祝日ファイルが存在しない場合は作成"""
        if not os.path.exists(self.holidays_file):
            os.makedirs(os.path.dirname(self.holidays_file), exist_ok=True)
            with open(self.holidays_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _load_holidays(self):
        """祝日データを読み込む"""
        try:
            with open(self.holidays_file, "r", encoding="utf-8") as f:
                self.holidays = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.holidays = {}
    
    def _save_holidays(self):
        """祝日データを保存"""
        with open(self.holidays_file, "w", encoding="utf-8") as f:
            json.dump(self.holidays, f, ensure_ascii=False, indent=2)
    
    def is_holiday(self, date: datetime) -> bool:
        """
        指定された日付が祝日かどうかを判定
        
        Args:
            date: 判定する日付
            
        Returns:
            祝日の場合True
        """
        date_str = date.strftime("%Y-%m-%d")
        # holidays.jsonのキーで祝日をチェック
        return date_str in self.holidays
    
    def get_holiday_before_date(self, date: datetime) -> Optional[str]:
        """
        指定された日付の前日が祝前日かどうかを判定
        
        Args:
            date: 判定する日付
            
        Returns:
            祝日前日の場合は祝日の日付文字列、そうでない場合はNone
        """
        tomorrow = date + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        # holidays.jsonのキーで祝日をチェック
        if tomorrow_str in self.holidays:
            return tomorrow_str
        return None
    
    def add_holiday(self, date: datetime, name: str = ""):
        """
        祝日を追加
        
        Args:
            date: 祝日の日付
            name: 祝日名
        """
        date_str = date.strftime("%Y-%m-%d")
        self.holidays[date_str] = name
        self._save_holidays()
    
    def remove_holiday(self, date: datetime):
        """
        祝日を削除
        
        Args:
            date: 削除する祝日の日付
        """
        date_str = date.strftime("%Y-%m-%d")
        if date_str in self.holidays:
            del self.holidays[date_str]
            self._save_holidays()
    
    def get_holidays_for_year(self, year: int) -> dict:
        """
        指定された年の祝日を取得
        
        Args:
            year: 年
            
        Returns:
            日付文字列をキー、祝日名を値とする辞書
        """
        year_holidays = {}
        for date_str, name in self.holidays.items():
            if date_str.startswith(f"{year}-"):
                year_holidays[date_str] = name
        return year_holidays

