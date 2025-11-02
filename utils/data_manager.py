"""データ管理機能"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import pytz


class DataManager:
    """回答データを管理するクラス"""
    
    def __init__(self, data_file: str = "data/responses.json"):
        """
        Args:
            data_file: データファイルのパス
        """
        self.data_file = data_file
        self.jst = pytz.timezone("Asia/Tokyo")
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """データファイルが存在しない場合は作成"""
        if not os.path.exists(self.data_file):
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _load_data(self) -> dict:
        """データを読み込む"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_data(self, data: dict):
        """データを保存"""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def save_response(
        self,
        user_id: int,
        date: datetime,
        can_attend: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ):
        """
        回答を保存
        
        Args:
            user_id: ユーザーID
            date: 回答日付
            can_attend: 参加可能かどうか
            start_time: 開始時刻（HH:MM形式）
            end_time: 終了時刻（HH:MM形式）
        """
        data = self._load_data()
        date_str = date.strftime("%Y-%m-%d")
        
        if date_str not in data:
            data[date_str] = []
        
        # 既存の回答を検索して更新、なければ追加
        response_found = False
        for response in data[date_str]:
            if response["user_id"] == user_id:
                response["can_attend"] = can_attend
                response["start_time"] = start_time
                response["end_time"] = end_time
                response["updated_at"] = datetime.now(self.jst).isoformat()
                response_found = True
                break
        
        if not response_found:
            data[date_str].append({
                "user_id": user_id,
                "can_attend": can_attend,
                "start_time": start_time,
                "end_time": end_time,
                "created_at": datetime.now(self.jst).isoformat(),
                "updated_at": datetime.now(self.jst).isoformat()
            })
        
        self._save_data(data)
    
    def get_responses_for_date(self, date: datetime) -> List[Dict]:
        """
        指定された日付の回答を取得
        
        Args:
            date: 日付
            
        Returns:
            回答データのリスト
        """
        data = self._load_data()
        date_str = date.strftime("%Y-%m-%d")
        return data.get(date_str, [])
    
    def get_attendable_users(self, date: datetime) -> List[Dict]:
        """
        指定された日付に参加可能なユーザーを取得
        
        Args:
            date: 日付
            
        Returns:
            参加可能なユーザーの回答データのリスト（登録時間の降順でソート）
        """
        all_responses = self.get_responses_for_date(date)
        attendable = [
            response for response in all_responses
            if response.get("can_attend", False)
        ]
        # 登録時間（updated_atまたはcreated_at）で降順にソート
        attendable.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
        return attendable
    
    def get_summary(self, date: datetime) -> Dict:
        """
        指定された日付の集計結果を取得
        
        Args:
            date: 日付
            
        Returns:
            集計結果の辞書
        """
        responses = self.get_responses_for_date(date)
        attendable = self.get_attendable_users(date)
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_responses": len(responses),
            "attendable_count": len(attendable),
            "attendable_users": [
                {
                    "user_id": r["user_id"],
                    "start_time": r.get("start_time"),
                    "end_time": r.get("end_time")
                }
                for r in attendable
            ],
            "not_attendable_count": len(responses) - len(attendable)
        }

