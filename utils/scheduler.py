"""スケジュール管理機能"""
import asyncio
from datetime import datetime, time, timedelta
from typing import List, Optional
import pytz
from utils.holidays import HolidayManager


class Scheduler:
    """メッセージ送信スケジュールを管理するクラス"""
    
    def __init__(self, config: dict):
        """
        Args:
            config: 設定辞書（weekdays, send_before_holidays, send_time, summary_timeを含む）
        """
        self.config = config
        self.jst = pytz.timezone("Asia/Tokyo")
        self.holiday_manager = HolidayManager()
        self.weekdays = config.get("weekdays", [4, 5])  # デフォルト: 金曜日、土曜日
        self.send_before_holidays = config.get("send_before_holidays", True)
        self.send_time = self._parse_time(config.get("send_time", "20:00"))
        self.summary_time = self._parse_time(config.get("summary_time", "22:00"))
        self.send_callback = None
        self.summary_callback = None
    
    def _parse_time(self, time_str: str) -> time:
        """
        時刻文字列をtimeオブジェクトに変換
        
        Args:
            time_str: "HH:MM"形式の時刻文字列
            
        Returns:
            timeオブジェクト
        """
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    
    def set_send_callback(self, callback):
        """送信コールバック関数を設定"""
        self.send_callback = callback
    
    def set_summary_callback(self, callback):
        """集計結果送信コールバック関数を設定"""
        self.summary_callback = callback
    
    def should_send_today(self, date: Optional[datetime] = None) -> bool:
        """
        今日メッセージを送信すべきかどうかを判定
        
        Args:
            date: 判定する日付（Noneの場合は現在日時）
            
        Returns:
            送信すべき場合True
        """
        if date is None:
            date = datetime.now(self.jst)
        else:
            if date.tzinfo is None:
                date = self.jst.localize(date)
        
        weekday = date.weekday()  # 0=月曜日, 6=日曜日
        
        # 曜日チェック
        if weekday in self.weekdays:
            return True
        
        # 祝前日チェック
        if self.send_before_holidays:
            holiday_date = self.holiday_manager.get_holiday_before_date(date)
            if holiday_date:
                return True
        
        return False
    
    _last_sent_minute = None  # クラス変数として追加
    
    async def check_and_send(self):
        """現在時刻をチェックして、送信時刻になったらメッセージを送信"""
        now = datetime.now(self.jst)
        current_time = now.time()
        
        # 送信時刻かどうかをチェック（同じ分内で重複送信を防ぐ）
        if (current_time.hour == self.send_time.hour and
            current_time.minute == self.send_time.minute):
            
            # 同じ分内で既に送信済みならスキップ
            current_minute_key = f"{now.year}-{now.month}-{now.day}-{current_time.hour}-{current_time.minute}"
            if hasattr(self, '_last_sent_minute') and self._last_sent_minute == current_minute_key:
                return
            
            should_send = self.should_send_today(now)
            print(f"[スケジューラー] {now.strftime('%Y-%m-%d %H:%M:%S')} - 送信時刻チェック: hour={current_time.hour}, minute={current_time.minute}, should_send={should_send}, weekday={now.weekday()}")
            
            if should_send:
                if self.send_callback:
                    print(f"[スケジューラー] メッセージを送信します")
                    await self.send_callback(now)
                    self._last_sent_minute = current_minute_key
                else:
                    print(f"[スケジューラー] エラー: send_callbackが設定されていません")
            else:
                print(f"[スケジューラー] 今日は送信対象外です（曜日チェックと祝前日チェック）")
    
    _last_sent_summary_minute = None  # クラス変数として追加
    
    async def check_and_send_summary(self):
        """現在時刻をチェックして、集計結果送信時刻になったらメッセージを送信"""
        now = datetime.now(self.jst)
        current_time = now.time()
        
        # 集計結果送信時刻かどうかをチェック（同じ分内で重複送信を防ぐ）
        if (current_time.hour == self.summary_time.hour and
            current_time.minute == self.summary_time.minute):
            
            # 同じ分内で既に送信済みならスキップ
            current_minute_key = f"{now.year}-{now.month}-{now.day}-{current_time.hour}-{current_time.minute}"
            if hasattr(self, '_last_sent_summary_minute') and self._last_sent_summary_minute == current_minute_key:
                return
            
            if self.summary_callback:
                print(f"[スケジューラー] 集計結果を送信します")
                await self.summary_callback(now)
                self._last_sent_summary_minute = current_minute_key
            else:
                print(f"[スケジューラー] エラー: summary_callbackが設定されていません")
    
    def get_next_send_datetime(self) -> Optional[datetime]:
        """
        次にメッセージを送信する日時を取得
        
        Returns:
            次に送信する日時、送信予定がない場合はNone
        """
        now = datetime.now(self.jst)
        current_date = now.date()
        
        # 次の7日間をチェック
        for i in range(1, 8):
            check_date = current_date + timedelta(days=i)
            check_datetime = datetime.combine(check_date, self.send_time)
            check_datetime = self.jst.localize(check_datetime)
            
            if self.should_send_today(check_datetime):
                return check_datetime
        
        return None

