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
        self._last_sent_minute = None
        self._last_sent_summary_minute = None
        # 予約リスト: [(datetime, time), ...] の形式で保存
        self.scheduled_sends: List[tuple] = []
    
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
    
    async def check_and_send(self):
        """現在時刻をチェックして、送信時刻になったらメッセージを送信"""
        now = datetime.now(self.jst)
        current_time = now.time()
        current_date = now.date()
        
        # 予約された送信をチェック
        scheduled_send = None
        for scheduled_date, scheduled_time in self.scheduled_sends:
            if (scheduled_date.date() == current_date and
                scheduled_time.hour == current_time.hour and
                scheduled_time.minute == current_time.minute):
                scheduled_send = scheduled_date
                break
        
        # 予約された送信がある場合
        if scheduled_send:
            current_minute_key = f"{now.year}-{now.month}-{now.day}-{current_time.hour}-{current_time.minute}"
            if hasattr(self, '_last_sent_minute') and self._last_sent_minute == current_minute_key:
                return
            
            print(f"[スケジューラー] {now.strftime('%Y-%m-%d %H:%M:%S')} - 予約された送信時刻: hour={current_time.hour}, minute={current_time.minute}")
            if self.send_callback:
                print(f"[スケジューラー] 予約されたメッセージを送信します")
                await self.send_callback(now)
                self._last_sent_minute = current_minute_key
                # 予約を削除
                self.scheduled_sends = [(d, t) for d, t in self.scheduled_sends if not (d.date() == current_date and t.hour == current_time.hour and t.minute == current_time.minute)]
                print(f"[スケジューラー] 予約を削除しました")
            else:
                print(f"[スケジューラー] エラー: send_callbackが設定されていません")
            return
        
        # 通常の送信時刻かどうかをチェック（同じ分内で重複送信を防ぐ）
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
    
    def add_scheduled_send(self, date: datetime, send_time: time):
        """
        予約送信を追加
        
        Args:
            date: 送信日（datetimeオブジェクト）
            send_time: 送信時刻（timeオブジェクト）
        """
        if date.tzinfo is None:
            date = self.jst.localize(date)
        else:
            date = date.astimezone(self.jst)
        
        # 既に同じ日時の予約がある場合は上書き
        date_only = date.date()
        self.scheduled_sends = [(d, t) for d, t in self.scheduled_sends if not (d.date() == date_only and t == send_time)]
        self.scheduled_sends.append((date, send_time))
        print(f"[スケジューラー] 予約を追加しました: {date.strftime('%Y-%m-%d')} {send_time.strftime('%H:%M')}")
    
    def remove_scheduled_send(self, date: datetime, send_time: Optional[time] = None):
        """
        予約送信を削除
        
        Args:
            date: 送信日（datetimeオブジェクト）
            send_time: 送信時刻（timeオブジェクト、Noneの場合はその日の全予約を削除）
        """
        if date.tzinfo is None:
            date = self.jst.localize(date)
        else:
            date = date.astimezone(self.jst)
        
        date_only = date.date()
        if send_time is None:
            # その日の全予約を削除
            self.scheduled_sends = [(d, t) for d, t in self.scheduled_sends if d.date() != date_only]
            print(f"[スケジューラー] 予約を削除しました: {date.strftime('%Y-%m-%d')} (全時刻)")
        else:
            # 特定の時刻の予約を削除
            self.scheduled_sends = [(d, t) for d, t in self.scheduled_sends if not (d.date() == date_only and t == send_time)]
            print(f"[スケジューラー] 予約を削除しました: {date.strftime('%Y-%m-%d')} {send_time.strftime('%H:%M')}")
    
    def get_scheduled_sends(self) -> List[tuple]:
        """
        予約送信の一覧を取得
        
        Returns:
            予約リスト: [(datetime, time), ...]
        """
        return sorted(self.scheduled_sends, key=lambda x: (x[0].date(), x[1]))
    
    def check_schedule_for_date(self, date: datetime) -> dict:
        """
        指定された日付の自動実行可否をチェック
        
        Args:
            date: チェックする日付（datetimeオブジェクト）
            
        Returns:
            チェック結果の辞書:
            {
                'will_send': bool,  # 送信されるかどうか
                'reason': str,  # 理由
                'weekday_match': bool,  # 曜日が一致するか
                'holiday_before': bool,  # 祝前日かどうか
                'scheduled': bool,  # 予約されているかどうか
                'scheduled_time': Optional[time]  # 予約されている時刻
            }
        """
        if date.tzinfo is None:
            date = self.jst.localize(date)
        else:
            date = date.astimezone(self.jst)
        
        weekday = date.weekday()
        weekday_match = weekday in self.weekdays
        
        holiday_before = False
        if self.send_before_holidays:
            holiday_date = self.holiday_manager.get_holiday_before_date(date)
            holiday_before = holiday_date is not None
        
        # 予約をチェック
        scheduled = False
        scheduled_time = None
        date_only = date.date()
        for scheduled_date, scheduled_t in self.scheduled_sends:
            if scheduled_date.date() == date_only:
                scheduled = True
                scheduled_time = scheduled_t
                break
        
        will_send = weekday_match or holiday_before or scheduled
        
        reason_parts = []
        if weekday_match:
            weekday_names = ['月', '火', '水', '木', '金', '土', '日']
            reason_parts.append(f"曜日が一致（{weekday_names[weekday]}曜日）")
        if holiday_before:
            reason_parts.append("祝前日")
        if scheduled:
            reason_parts.append(f"予約済み（{scheduled_time.strftime('%H:%M')}）")
        if not will_send:
            reason_parts.append("送信対象外")
        
        reason = "、".join(reason_parts) if reason_parts else "送信対象外"
        
        return {
            'will_send': will_send,
            'reason': reason,
            'weekday_match': weekday_match,
            'holiday_before': holiday_before,
            'scheduled': scheduled,
            'scheduled_time': scheduled_time
        }

