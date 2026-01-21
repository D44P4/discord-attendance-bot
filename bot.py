"""Discordボットメインファイル"""
import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
import argparse
from datetime import datetime, time
import pytz
from dotenv import load_dotenv
from utils.scheduler import Scheduler
from utils.data_manager import DataManager
from utils.holidays import HolidayManager
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# .envファイルを読み込む（ローカル環境向け）
load_dotenv()


# Botの設定を読み込み
def load_config():
    """設定ファイルを読み込む（環境変数優先）"""
    # 環境変数から読み込む（.envファイルまたはRailway等のクラウド環境向け）
    discord_token = os.environ.get("DISCORD_TOKEN")
    if discord_token:
        config = {
            "token": discord_token,
            "guild_id": os.environ.get("GUILD_ID", ""),
            "channel_id": os.environ.get("CHANNEL_ID", ""),
            "auto_send_channel_id": os.environ.get("AUTO_SEND_CHANNEL_ID", ""),
            "send_time": os.environ.get("SEND_TIME", "19:00"),
            "summary_time": os.environ.get("SUMMARY_TIME", "22:00"),
            "weekdays": json.loads(os.environ.get("WEEKDAYS", "[4,5]")),
            "send_before_holidays": os.environ.get("SEND_BEFORE_HOLIDAYS", "true").lower() == "true"
        }
        return config
    
    # 設定ファイルから読み込む（ローカル環境向け）
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            # summary_timeが存在しない場合はデフォルト値を設定
            if "summary_time" not in config_data:
                config_data["summary_time"] = "22:00"
            return config_data
    else:
        # 環境変数も設定ファイルもない場合はエラー
        raise ValueError(
            "設定が見つかりません。環境変数DISCORD_TOKENを設定するか、"
            "config.jsonファイルを作成してください。"
        )


# Intentsの設定
intents = discord.Intents.default()
# intents.message_content = True  # 必要に応じてDiscord Developer Portalで有効化してください（スラッシュコマンドのみの場合は不要）
# intents.members = True  # 必要に応じてDiscord Developer Portalで有効化してください

# Botの初期化
config = load_config()
bot = commands.Bot(command_prefix="!", intents=intents)

# ユーティリティの初期化
scheduler = Scheduler(config)
data_manager = DataManager()
holiday_manager = HolidayManager()

def create_scheduler_task():
    """スケジューラータスクを作成"""
    @tasks.loop(minutes=1)
    async def scheduler_task():
        """定期メッセージ送信タスク"""
        await scheduler.check_and_send()
        # 集計結果送信チェック
        await scheduler.check_and_send_summary()
    return scheduler_task

# スケジューラータスクの初期化
scheduler_task = create_scheduler_task()

async def restart_scheduler():
    """スケジューラーを再起動（設定変更時に呼び出す）"""
    global scheduler_task
    if scheduler_task and scheduler_task.is_running():
        scheduler_task.cancel()
        # タスクが完全に停止するまで待機
        while scheduler_task.is_running():
            await asyncio.sleep(0.1)
    scheduler_task = create_scheduler_task()
    scheduler_task.start()
    print("[スケジューラー] スケジューラーを再起動しました")


async def sync_commands(force_guild_only: bool = False):
    """コマンドを同期（サーバー限定とグローバルの両方を試す）"""
    try:
        guild_id = config.get("guild_id")
        synced_commands = []
        
        # コマンドツリーに登録されているコマンドを確認
        all_commands_before = [cmd.name for cmd in bot.tree.get_commands()]
        print(f"[コマンド同期] 同期前のコマンド一覧: {all_commands_before}")
        
        if not all_commands_before:
            print(f"[コマンド同期] 警告: コマンドが定義されていません。待機してから再試行します。")
            await asyncio.sleep(3)
            all_commands_before = [cmd.name for cmd in bot.tree.get_commands()]
            print(f"[コマンド同期] 再確認後のコマンド一覧: {all_commands_before}")
        
        # Discord APIの準備を待つ
        await asyncio.sleep(2)
        
        # まずサーバー限定で同期（即座に反映）
        guild_sync_success = False
        guild_sync_count = 0
        if guild_id and str(guild_id).strip():
            try:
                guild = discord.Object(id=int(guild_id))
                print(f"[コマンド同期] サーバー限定同期を開始します（guild_id: {guild_id}）")
                synced_guild = await bot.tree.sync(guild=guild)
                guild_sync_count = len(synced_guild)
                synced_commands.extend([cmd.name for cmd in synced_guild])
                print(f"[コマンド同期] サーバー限定で {guild_sync_count} 個のコマンドを同期しました: {[cmd.name for cmd in synced_guild]}")
                
                # サーバー限定同期が成功した場合（1個以上同期された場合）
                if guild_sync_count > 0:
                    guild_sync_success = True
                    # サーバー限定同期が成功した場合、少し待つ
                    await asyncio.sleep(1)
                else:
                    print(f"[コマンド同期] 警告: サーバー限定同期で0個のコマンドが返されました。グローバル同期を試行します。")
            except (ValueError, TypeError) as e:
                print(f"[コマンド同期] サーバー限定コマンドの同期をスキップしました（guild_idが無効）: {e}")
            except Exception as e:
                print(f"[コマンド同期] サーバー限定同期でエラーが発生しました: {e}")
                import traceback
                traceback.print_exc()
        
        # グローバル同期は、サーバー限定同期が失敗した場合、または0個の場合、またはforce_guild_onlyがFalseの場合のみ実行
        # サーバー限定同期が0個の場合は、force_guild_onlyに関係なくグローバル同期を試行
        print(f"[コマンド同期] デバッグ: force_guild_only={force_guild_only}, guild_sync_success={guild_sync_success}, guild_sync_count={guild_sync_count}")
        
        should_run_global = (not force_guild_only and (not guild_sync_success or guild_sync_count == 0)) or (force_guild_only and guild_sync_count == 0)
        print(f"[コマンド同期] デバッグ: should_run_global={should_run_global}")
        
        if should_run_global:
            try:
                if guild_sync_count == 0:
                    print(f"[コマンド同期] グローバル同期を開始します（サーバー限定同期で0個のコマンドが返されたため）")
                else:
                    print(f"[コマンド同期] グローバル同期を開始します（サーバー限定同期が失敗したため）")
                synced_global = await bot.tree.sync()
                synced_commands.extend([cmd.name for cmd in synced_global])
                print(f"[コマンド同期] グローバルで {len(synced_global)} 個のコマンドを同期しました: {[cmd.name for cmd in synced_global]}")
            except Exception as e:
                print(f"[コマンド同期] グローバル同期でエラーが発生しました: {e}")
                import traceback
                traceback.print_exc()
        elif force_guild_only and guild_sync_success:
            print(f"[コマンド同期] サーバー限定同期のみを実行しました（グローバル同期はスキップ）")
        elif guild_sync_success:
            print(f"[コマンド同期] サーバー限定同期が成功したため、グローバル同期はスキップしました（即座に反映されます）")
        else:
            print(f"[コマンド同期] デバッグ: 予期しない条件分岐に入りました")
        
        # 全コマンドの一覧を表示
        all_commands = set(synced_commands)
        print(f"[コマンド同期] 同期された全コマンド（{len(all_commands)}個）: {sorted(all_commands)}")
        
        # 期待されるコマンドと比較
        expected_commands = {"send_question", "show_summary", "set_send_time", "set_summary_time", "view_auto_times", "sync_commands"}
        missing_commands = expected_commands - all_commands
        if missing_commands:
            print(f"[コマンド同期] 警告: 以下のコマンドが同期されていません: {sorted(missing_commands)}")
        else:
            print(f"[コマンド同期] すべてのコマンドが正常に同期されました")
        
        return all_commands
        
    except Exception as e:
        print(f"[コマンド同期] コマンドの同期に失敗しました: {e}")
        import traceback
        traceback.print_exc()
        return set()


@bot.event
async def on_ready():
    """Bot起動時の処理"""
    print(f"{bot.user} がログインしました")
    
    # 少し待ってからコマンドを同期（Discord APIの準備を待つ）
    await asyncio.sleep(2)
    
    # テスト用: 即座にメッセージを送信
    global force_send_flag
    if force_send_flag:
        await asyncio.sleep(2)  # ボットが完全に準備できるまで少し待つ
        # 自動送信用のチャンネルIDを取得（設定されていない場合は通常のchannel_idを使用）
        auto_send_channel_id = config.get("auto_send_channel_id") or config.get("channel_id")
        if auto_send_channel_id:
            channel = bot.get_channel(int(auto_send_channel_id))
            if channel:
                now = datetime.now(pytz.timezone("Asia/Tokyo"))
                await send_question_message(channel, now)
                print(f"[テスト] メッセージを即座に送信しました（チャンネルID: {auto_send_channel_id}）")
                force_send_flag = False  # フラグをリセット
            else:
                print(f"[テスト] エラー: チャンネルが見つかりません。channel_id={auto_send_channel_id}")
        else:
            print(f"[テスト] エラー: channel_idが設定されていません")
    
    # スケジューラーのコールバックを設定
    scheduler.set_send_callback(scheduled_send_callback)
    scheduler.set_summary_callback(scheduled_summary_callback)
    
    # スケジュールチェックタスクを開始
    global scheduler_task
    if scheduler_task is None:
        scheduler_task = create_scheduler_task()
    if not scheduler_task.is_running():
        scheduler_task.start()
    
    # コマンドが定義されるまで待つ（ファイル読み込み完了を待つ）
    await asyncio.sleep(3)
    
    # コマンドツリーに登録されているコマンドを確認
    all_commands = [cmd.name for cmd in bot.tree.get_commands()]
    print(f"[コマンド確認] 定義されているコマンド: {all_commands}")
    
    if not all_commands:
        print(f"[コマンド確認] 警告: コマンドが定義されていません。もう少し待ってから再試行します。")
        await asyncio.sleep(5)
        all_commands = [cmd.name for cmd in bot.tree.get_commands()]
        print(f"[コマンド確認] 再確認後のコマンド: {all_commands}")
    
    # コマンドを同期（サーバー限定同期を優先）
    guild_id = config.get("guild_id")
    if guild_id and str(guild_id).strip():
        # サーバー限定同期のみを実行（即座に反映される）
        await sync_commands(force_guild_only=True)
    else:
        # guild_idが設定されていない場合はグローバル同期
        await sync_commands(force_guild_only=False)


async def scheduled_summary_callback(date: datetime):
    """スケジュール集計結果送信コールバック"""
    print(f"[コールバック] 集計結果送信コールバックが呼ばれました: {date.strftime('%Y-%m-%d %H:%M:%S')}")
    date_str = date.strftime("%Y-%m-%d")
    
    # 今日メッセージを送信したかチェック
    if date_str in sent_dates:
        # 自動送信用のチャンネルIDを取得（設定されていない場合は通常のchannel_idを使用）
        auto_send_channel_id = config.get("auto_send_channel_id") or config.get("channel_id")
        if auto_send_channel_id:
            channel = bot.get_channel(int(auto_send_channel_id))
            if channel:
                summary = data_manager.get_summary(date)
                
                embed = discord.Embed(
                    title=f"{summary['date']} の集計結果",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="総回答数",
                    value=f"{summary['total_responses']}件",
                    inline=True
                )
                
                embed.add_field(
                    name="参加可能",
                    value=f"{summary['attendable_count']}人",
                    inline=True
                )
                
                embed.add_field(
                    name="参加不可",
                    value=f"{summary['not_attendable_count']}人",
                    inline=True
                )
                
                if summary['attendable_users']:
                    user_list = []
                    for user_data in summary['attendable_users']:
                        user_id = user_data['user_id']
                        start_time = user_data.get('start_time', '未設定')
                        end_time = user_data.get('end_time', '未設定')
                        # 表示用に00:00を24:00に変換
                        start_time_display = format_time_display(start_time) if start_time != '未設定' else start_time
                        end_time_display = format_time_display(end_time) if end_time != '未設定' else end_time
                        user_list.append(f"<@{user_id}>: {start_time_display} ～ {end_time_display}")
                    
                    embed.add_field(
                        name="参加可能なユーザー",
                        value="\n".join(user_list) if user_list else "なし",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="参加可能なユーザー",
                        value="なし",
                        inline=False
                    )
                
                await channel.send(embed=embed)
                # 送信済みフラグを削除（1日1回のみ送信）
                sent_dates.discard(date_str)
                print(f"[コールバック] 集計結果を送信しました。送信日付を削除: {date_str}")
            else:
                print(f"[コールバック] エラー: チャンネルが見つかりません。channel_id={auto_send_channel_id}")
        else:
            print(f"[コールバック] エラー: channel_idが設定されていません")


async def send_question_message(channel: discord.TextChannel, date: datetime = None):
    """
    質問メッセージを送信
    
    Args:
        channel: 送信先チャンネル
        date: 対象日付（Noneの場合は今日）
    """
    try:
        if date is None:
            date = datetime.now(pytz.timezone("Asia/Tokyo"))
        
        date_str = date.strftime("%Y年%m月%d日")
        
        embed = discord.Embed(
            title="参加可否の確認",
            description=f"{date_str}に参加可能ですか？",
            color=discord.Color.blue()
        )
        
        # ボタンの作成
        view = AttendanceView(date)
        
        await channel.send(embed=embed, view=view)
    except Exception as e:
        print(f"send_question_messageでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        raise


# スケジューラーのコールバックを設定
# メッセージ送信日を記録（集計結果送信用）
sent_dates = set()
force_send_flag = False  # テスト用: 即座にメッセージを送信するフラグ

async def scheduled_send_callback(date: datetime):
    """スケジュール送信コールバック"""
    print(f"[コールバック] メッセージ送信コールバックが呼ばれました: {date.strftime('%Y-%m-%d %H:%M:%S')}")
    # 自動送信用のチャンネルIDを取得（設定されていない場合は通常のchannel_idを使用）
    auto_send_channel_id = config.get("auto_send_channel_id") or config.get("channel_id")
    if auto_send_channel_id:
        channel = bot.get_channel(int(auto_send_channel_id))
        if channel:
            print(f"[コールバック] チャンネルが見つかりました: {channel.name}")
            await send_question_message(channel, date)
            # 送信した日付を記録（集計結果送信用）
            date_str = date.strftime("%Y-%m-%d")
            sent_dates.add(date_str)
            print(f"[コールバック] メッセージを送信しました。送信日付を記録: {date_str}")
        else:
            print(f"[コールバック] エラー: チャンネルが見つかりません。channel_id={auto_send_channel_id}")
    else:
        print(f"[コールバック] エラー: channel_idが設定されていません")


scheduler.set_send_callback(scheduled_send_callback)


class AttendanceView(discord.ui.View):
    """参加可否選択用のビュー"""
    
    def __init__(self, date: datetime):
        super().__init__(timeout=None)
        self.date = date
    
    @discord.ui.button(label="参加可能", style=discord.ButtonStyle.success, emoji="✅")
    async def can_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        """参加可能ボタンが押されたときの処理"""
        try:
            await interaction.response.send_message(
                "参加可能時間帯を選択してください",
                view=TimeSelectionView(self.date, interaction.user.id, True),
                ephemeral=True
            )
        except Exception as e:
            print(f"can_attendボタンでエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "エラーが発生しました。管理者に連絡してください。",
                        ephemeral=True
                    )
            except:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
    
    @discord.ui.button(label="参加不可", style=discord.ButtonStyle.danger, emoji="❌")
    async def cannot_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        """参加不可ボタンが押されたときの処理"""
        data_manager.save_response(
            user_id=interaction.user.id,
            date=self.date,
            can_attend=False
        )
        
        await interaction.response.send_message(
            "回答を記録しました。ありがとうございます！",
            ephemeral=True
        )


def format_time_display(time_str: str) -> str:
    """時刻表示を整形（00:00を24:00に変換）"""
    if time_str == "00:00":
        return "24:00"
    return time_str


class TimeSelectionView(discord.ui.View):
    """時刻選択用のビュー"""
    
    def __init__(self, date: datetime, user_id: int, can_attend: bool, start_time: str = None, end_time: str = None):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.date = date
        self.user_id = user_id
        self.can_attend = can_attend
        self.start_time = start_time
        self.end_time = end_time
        
        # 開始時刻選択ドロップダウン（30分単位）
        start_placeholder = f"開始時刻を選択{' (選択済み: ' + self.start_time + ')' if self.start_time else ''}"
        self.start_time_select = discord.ui.Select(
            placeholder=start_placeholder[:100],  # Discordのプレースホルダーは100文字制限
            options=self._create_time_options("start")
        )
        self.start_time_select.callback = self._start_time_callback
        self.add_item(self.start_time_select)
        
        # 終了時刻選択ドロップダウン（30分単位）
        end_placeholder = f"終了時刻を選択{' (選択済み: ' + self.end_time + ')' if self.end_time else ''}"
        self.end_time_select = discord.ui.Select(
            placeholder=end_placeholder[:100],
            options=self._create_time_options("end")
        )
        self.end_time_select.callback = self._end_time_callback
        self.add_item(self.end_time_select)
        
        # 確定ボタン（どちらか一方が選択されていれば有効）
        self.confirm_button = discord.ui.Button(
            label="確定",
            style=discord.ButtonStyle.primary,
            disabled=not (self.start_time or self.end_time)
        )
        self.confirm_button.callback = self._confirm_callback
        self.add_item(self.confirm_button)
    
    def _create_time_options(self, select_type: str = "start"):
        """時刻選択オプションを作成（30分単位、降順、24:00～20:00）"""
        # 24:00（0:00）から20:00まで30分刻みで降順
        # 24:00, 23:30, 23:00, 22:30, 22:00, 21:30, 21:00, 20:30, 20:00
        all_options = []
        
        # 24:00（0:00）を最初に追加
        all_options.append(
            discord.SelectOption(
                label="24:00",
                value="00:00",
                description="24:00に設定"
            )
        )
        
        # 23:30から20:00まで30分刻みで降順
        for hour in range(23, 19, -1):  # 23時から20時まで降順
            for minute in [30, 0]:  # 30分、0分の順（降順）
                time_str = f"{hour:02d}:{minute:02d}"
                all_options.append(
                    discord.SelectOption(
                        label=time_str,
                        value=time_str,
                        description=f"{time_str}に設定"
                    )
                )
        
        # DiscordのSelectは25個までなので、開始時刻と終了時刻で範囲を分ける
        # 全9個なので、両方とも同じリストを使用可能
        # ただし、開始時刻と終了時刻で同じリストを使うと混乱する可能性があるため、
        # 開始時刻用と終了時刻用で同じリストを返す（9個なので25個以内）
        return all_options
    
    async def _start_time_callback(self, interaction: discord.Interaction):
        """開始時刻が選択されたときの処理"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "あなたの回答ではありません。",
                ephemeral=True
            )
            return
        
        self.start_time = interaction.data["values"][0]
        
        # 確定ボタンの状態を更新（どちらか一方でも選択されていれば有効）
        if self.start_time or self.end_time:
            self.confirm_button.disabled = False
        else:
            self.confirm_button.disabled = True
        
        # メッセージを更新して確定ボタンの状態を反映
        view = TimeSelectionView(self.date, self.user_id, self.can_attend)
        view.start_time = self.start_time
        view.end_time = self.end_time
        if view.start_time or view.end_time:
            view.confirm_button.disabled = False
        else:
            view.confirm_button.disabled = True
        
        await interaction.response.edit_message(
            content=f"参加可能時間帯を選択してください\n\n開始時刻: {format_time_display(self.start_time) if self.start_time else '未選択'}\n終了時刻: {format_time_display(self.end_time) if self.end_time else '未選択'}",
            view=view
        )
    
    async def _end_time_callback(self, interaction: discord.Interaction):
        """終了時刻が選択されたときの処理"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "あなたの回答ではありません。",
                ephemeral=True
            )
            return
        
        self.end_time = interaction.data["values"][0]
        
        # 確定ボタンの状態を更新（どちらか一方でも選択されていれば有効）
        if self.start_time or self.end_time:
            self.confirm_button.disabled = False
        else:
            self.confirm_button.disabled = True
        
        # メッセージを更新して確定ボタンの状態を反映
        view = TimeSelectionView(self.date, self.user_id, self.can_attend)
        view.start_time = self.start_time
        view.end_time = self.end_time
        if view.start_time or view.end_time:
            view.confirm_button.disabled = False
        else:
            view.confirm_button.disabled = True
        
        await interaction.response.edit_message(
            content=f"参加可能時間帯を選択してください\n\n開始時刻: {self.start_time or '未選択'}\n終了時刻: {self.end_time or '未選択'}",
            view=view
        )
    
    async def _confirm_callback(self, interaction: discord.Interaction):
        """確定ボタンが押されたときの処理"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "あなたの回答ではありません。",
                ephemeral=True
            )
            return
        
        # どちらか一方でも選択されていればOK
        if not self.start_time and not self.end_time:
            await interaction.response.send_message(
                "開始時刻または終了時刻のどちらかを選択してください。",
                ephemeral=True
            )
            return
        
        # データを保存
        data_manager.save_response(
            user_id=self.user_id,
            date=self.date,
            can_attend=self.can_attend,
            start_time=self.start_time,
            end_time=self.end_time
        )
        
        # メッセージの組み立て
        if self.start_time and self.end_time:
            message = f"回答を記録しました。\n参加可能時間: {format_time_display(self.start_time)} ～ {format_time_display(self.end_time)}"
        elif self.start_time:
            message = f"回答を記録しました。\n参加可能開始時刻: {format_time_display(self.start_time)}"
        else:
            message = f"回答を記録しました。\n参加可能終了時刻: {format_time_display(self.end_time)}"
        
        await interaction.response.send_message(
            message,
            ephemeral=True
        )
        
        # ビューを無効化
        self.stop()


@bot.tree.command(name="send_question", description="参加可否の質問メッセージを手動で送信")
async def send_question(interaction: discord.Interaction):
    """手動で質問メッセージを送信"""
    try:
        if not interaction.channel:
            await interaction.response.send_message(
                "チャンネルが見つかりません。",
                ephemeral=True
            )
            return
        
        # 指定されたチャンネルでのみコマンドを実行可能
        # channel_idとauto_send_channel_idの両方で実行可能
        allowed_channel_id = config.get("channel_id")
        auto_send_channel_id = config.get("auto_send_channel_id")
        
        # どちらかのチャンネルで実行されているかチェック
        is_allowed_channel = (
            (not allowed_channel_id and not auto_send_channel_id) or  # チャンネル制限がない場合
            (allowed_channel_id and str(interaction.channel.id) == str(allowed_channel_id)) or  # channel_idと一致
            (auto_send_channel_id and str(interaction.channel.id) == str(auto_send_channel_id))  # auto_send_channel_idと一致
        )
        
        if not is_allowed_channel:
            await interaction.response.send_message(
                f"このコマンドは指定されたチャンネルでのみ使用できます。",
                ephemeral=True
            )
            return
        
        # 質問メッセージを送信
        date = datetime.now(pytz.timezone("Asia/Tokyo"))
        date_str = date.strftime("%Y年%m月%d日")
        
        embed = discord.Embed(
            title="参加可否の確認",
            description=f"{date_str}に参加可能ですか？",
            color=discord.Color.blue()
        )
        
        # ボタンの作成
        view = AttendanceView(date)
        
        await interaction.response.send_message(
            embed=embed,
            view=view
        )
    except Exception as e:
        print(f"send_questionコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="show_summary", description="集計結果を表示")
async def show_summary(interaction: discord.Interaction):
    """集計結果を表示"""
    # 指定されたチャンネルでのみコマンドを実行可能
    # channel_idとauto_send_channel_idの両方で実行可能
    allowed_channel_id = config.get("channel_id")
    auto_send_channel_id = config.get("auto_send_channel_id")
    
    # どちらかのチャンネルで実行されているかチェック
    is_allowed_channel = (
        (not allowed_channel_id and not auto_send_channel_id) or  # チャンネル制限がない場合
        (allowed_channel_id and str(interaction.channel.id) == str(allowed_channel_id)) or  # channel_idと一致
        (auto_send_channel_id and str(interaction.channel.id) == str(auto_send_channel_id))  # auto_send_channel_idと一致
    )
    
    if not is_allowed_channel:
        await interaction.response.send_message(
            f"このコマンドは指定されたチャンネルでのみ使用できます。",
            ephemeral=True
        )
        return
    
    date = datetime.now(pytz.timezone("Asia/Tokyo"))
    summary = data_manager.get_summary(date)
    
    embed = discord.Embed(
        title=f"{summary['date']} の集計結果",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="総回答数",
        value=f"{summary['total_responses']}件",
        inline=True
    )
    
    embed.add_field(
        name="参加可能",
        value=f"{summary['attendable_count']}人",
        inline=True
    )
    
    embed.add_field(
        name="参加不可",
        value=f"{summary['not_attendable_count']}人",
        inline=True
    )
    
    if summary['attendable_users']:
        user_list = []
        for user_data in summary['attendable_users']:
            user_id = user_data['user_id']
            start_time = user_data.get('start_time', '未設定')
            end_time = user_data.get('end_time', '未設定')
            # 表示用に00:00を24:00に変換
            start_time_display = format_time_display(start_time) if start_time != '未設定' else start_time
            end_time_display = format_time_display(end_time) if end_time != '未設定' else end_time
            user_list.append(f"<@{user_id}>: {start_time_display} ～ {end_time_display}")
        
        embed.add_field(
            name="参加可能なユーザー",
            value="\n".join(user_list) if user_list else "なし",
            inline=False
        )
    else:
        embed.add_field(
            name="参加可能なユーザー",
            value="なし",
            inline=False
        )
    
    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"show_summaryコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


def validate_time_format(time_str: str) -> bool:
    """時間形式（HH:MM）を検証"""
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return False
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return False
        return True
    except (ValueError, AttributeError):
        return False


def validate_date_format(date_str: str) -> bool:
    """日付形式（YYYY-MM-DD）を検証"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, AttributeError):
        return False


def save_config_to_file(config_data: dict):
    """設定をconfig.jsonに保存"""
    config_path = "config.json"
    # 環境変数が設定されている場合は、config.jsonに保存しない
    if os.environ.get("DISCORD_TOKEN"):
        print("[設定] 環境変数が設定されているため、config.jsonには保存しません")
        return
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_config = {}
    
    # 既存の設定を更新（トークンなどの機密情報は保持）
    for key, value in config_data.items():
        if key != "token":  # トークンは保存しない
            existing_config[key] = value
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing_config, f, ensure_ascii=False, indent=2)
    print(f"[設定] config.jsonに保存しました: {list(config_data.keys())}")


@bot.tree.command(name="set_send_time", description="send_questionの自動実行時間を設定")
async def set_send_time(interaction: discord.Interaction, time: str):
    """send_questionの自動実行時間を設定"""
    try:
        # 時間形式の検証
        if not validate_time_format(time):
            await interaction.response.send_message(
                "時間形式が正しくありません。HH:MM形式で指定してください（例: 19:00）。",
                ephemeral=True
            )
            return
        
        # 即座に応答を送信（タイムアウトを防ぐ）
        await interaction.response.defer(ephemeral=True)
        
        # 設定を更新
        config["send_time"] = time
        scheduler.send_time = scheduler._parse_time(time)
        
        # config.jsonに保存（環境変数が設定されていない場合のみ）
        save_config_to_file({"send_time": time})
        
        # スケジューラーを再起動
        await restart_scheduler()
        
        # 完了メッセージを送信
        await interaction.followup.send(
            f"send_questionの自動実行時間を {time} に設定しました。",
            ephemeral=True
        )
    except Exception as e:
        print(f"set_send_timeコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="set_summary_time", description="show_summaryの自動実行時間を設定")
async def set_summary_time(interaction: discord.Interaction, time: str):
    """show_summaryの自動実行時間を設定"""
    try:
        # 時間形式の検証
        if not validate_time_format(time):
            await interaction.response.send_message(
                "時間形式が正しくありません。HH:MM形式で指定してください（例: 22:00）。",
                ephemeral=True
            )
            return
        
        # 即座に応答を送信（タイムアウトを防ぐ）
        await interaction.response.defer(ephemeral=True)
        
        # 設定を更新
        config["summary_time"] = time
        scheduler.summary_time = scheduler._parse_time(time)
        
        # config.jsonに保存（環境変数が設定されていない場合のみ）
        save_config_to_file({"summary_time": time})
        
        # スケジューラーを再起動
        await restart_scheduler()
        
        # 完了メッセージを送信
        await interaction.followup.send(
            f"show_summaryの自動実行時間を {time} に設定しました。",
            ephemeral=True
        )
    except Exception as e:
        print(f"set_summary_timeコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="view_auto_times", description="自動実行時間の設定を確認")
async def view_auto_times(interaction: discord.Interaction):
    """自動実行時間の設定を確認"""
    try:
        # 現在の設定を取得
        send_time = config.get("send_time", "20:00")
        summary_time = config.get("summary_time", "22:00")
        
        # 設定元を確認
        is_env_send = os.environ.get("SEND_TIME") is not None
        is_env_summary = os.environ.get("SUMMARY_TIME") is not None
        
        embed = discord.Embed(
            title="自動実行時間の設定",
            color=discord.Color.blue()
        )
        
        send_source = "環境変数" if is_env_send else "config.json"
        summary_source = "環境変数" if is_env_summary else "config.json"
        
        embed.add_field(
            name="send_questionの実行時間",
            value=f"{send_time} ({send_source})",
            inline=False
        )
        
        embed.add_field(
            name="show_summaryの実行時間",
            value=f"{summary_time} ({summary_source})",
            inline=False
        )
        
        if is_env_send or is_env_summary:
            embed.set_footer(
                text="環境変数が設定されている場合、コマンドで変更しても環境変数が優先されます。"
            )
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"view_auto_timesコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="check_schedule", description="指定された日付に自動実行されるかどうかを確認")
async def check_schedule(interaction: discord.Interaction, date: str = None):
    """指定された日付に自動実行されるかどうかを確認"""
    try:
        # 日付が指定されていない場合は今日
        if date is None:
            target_date = datetime.now(pytz.timezone("Asia/Tokyo"))
        else:
            # 日付形式の検証
            if not validate_date_format(date):
                await interaction.response.send_message(
                    "日付形式が正しくありません。YYYY-MM-DD形式で指定してください（例: 2025-11-24）。",
                    ephemeral=True
                )
                return
            
            # 日付をdatetimeオブジェクトに変換
            target_date = datetime.strptime(date, "%Y-%m-%d")
            target_date = pytz.timezone("Asia/Tokyo").localize(target_date)
        
        # スケジュールをチェック
        result = scheduler.check_schedule_for_date(target_date)
        
        # 結果を埋め込みメッセージで表示
        embed = discord.Embed(
            title=f"{target_date.strftime('%Y年%m月%d日')} の自動実行確認",
            color=discord.Color.green() if result['will_send'] else discord.Color.red()
        )
        
        embed.add_field(
            name="送信されるか",
            value="✅ 送信されます" if result['will_send'] else "❌ 送信されません",
            inline=False
        )
        
        embed.add_field(
            name="理由",
            value=result['reason'],
            inline=False
        )
        
        # 詳細情報
        details = []
        details.append(f"曜日一致: {'✅' if result['weekday_match'] else '❌'}")
        details.append(f"祝前日: {'✅' if result['holiday_before'] else '❌'}")
        details.append(f"予約済み: {'✅' if result['scheduled'] else '❌'}")
        if result['scheduled_time']:
            details.append(f"予約時刻: {result['scheduled_time'].strftime('%H:%M')}")
        
        embed.add_field(
            name="詳細",
            value="\n".join(details),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"check_scheduleコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="schedule_send", description="指定された日時にメッセージを送信するように予約")
async def schedule_send(interaction: discord.Interaction, date: str, time: str = None):
    """指定された日時にメッセージを送信するように予約"""
    try:
        # 日付形式の検証
        if not validate_date_format(date):
            await interaction.response.send_message(
                "日付形式が正しくありません。YYYY-MM-DD形式で指定してください（例: 2025-11-24）。",
                ephemeral=True
            )
            return
        
        # 時刻が指定されていない場合は設定済みのsend_timeを使用
        if time is None:
            send_time = scheduler.send_time
        else:
            # 時刻形式の検証
            if not validate_time_format(time):
                await interaction.response.send_message(
                    "時刻形式が正しくありません。HH:MM形式で指定してください（例: 20:00）。",
                    ephemeral=True
                )
                return
            send_time = scheduler._parse_time(time)
        
        # 日付をdatetimeオブジェクトに変換
        target_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = pytz.timezone("Asia/Tokyo").localize(target_date)
        target_date = datetime.combine(target_date.date(), send_time)
        target_date = pytz.timezone("Asia/Tokyo").localize(target_date)
        
        # 過去の日付でないかチェック
        now = datetime.now(pytz.timezone("Asia/Tokyo"))
        if target_date < now:
            await interaction.response.send_message(
                "過去の日時は予約できません。未来の日時を指定してください。",
                ephemeral=True
            )
            return
        
        # 予約を追加
        scheduler.add_scheduled_send(target_date, send_time)
        
        await interaction.response.send_message(
            f"予約を追加しました: {target_date.strftime('%Y年%m月%d日 %H:%M')}",
            ephemeral=True
        )
    except Exception as e:
        print(f"schedule_sendコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="list_schedules", description="予約されている送信の一覧を表示")
async def list_schedules(interaction: discord.Interaction):
    """予約されている送信の一覧を表示"""
    try:
        scheduled_sends = scheduler.get_scheduled_sends()
        
        if not scheduled_sends:
            await interaction.response.send_message(
                "予約されている送信はありません。",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="予約されている送信一覧",
            color=discord.Color.blue()
        )
        
        schedule_list = []
        for i, (scheduled_date, scheduled_time) in enumerate(scheduled_sends, 1):
            schedule_list.append(
                f"{i}. {scheduled_date.strftime('%Y年%m月%d日')} {scheduled_time.strftime('%H:%M')}"
            )
        
        embed.add_field(
            name=f"予約数: {len(scheduled_sends)}件",
            value="\n".join(schedule_list) if schedule_list else "なし",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"list_schedulesコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="cancel_schedule", description="予約されている送信をキャンセル")
async def cancel_schedule(interaction: discord.Interaction, date: str, time: str = None):
    """予約されている送信をキャンセル"""
    try:
        # 日付形式の検証
        if not validate_date_format(date):
            await interaction.response.send_message(
                "日付形式が正しくありません。YYYY-MM-DD形式で指定してください（例: 2025-11-24）。",
                ephemeral=True
            )
            return
        
        # 時刻が指定されている場合は時刻形式の検証
        send_time = None
        if time is not None:
            if not validate_time_format(time):
                await interaction.response.send_message(
                    "時刻形式が正しくありません。HH:MM形式で指定してください（例: 20:00）。",
                    ephemeral=True
                )
                return
            send_time = scheduler._parse_time(time)
        
        # 日付をdatetimeオブジェクトに変換
        target_date = datetime.strptime(date, "%Y-%m-%d")
        target_date = pytz.timezone("Asia/Tokyo").localize(target_date)
        
        # 予約を削除
        scheduler.remove_scheduled_send(target_date, send_time)
        
        if send_time:
            await interaction.response.send_message(
                f"予約をキャンセルしました: {target_date.strftime('%Y年%m月%d日')} {send_time.strftime('%H:%M')}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"予約をキャンセルしました: {target_date.strftime('%Y年%m月%d日')} (全時刻)",
                ephemeral=True
            )
    except Exception as e:
        print(f"cancel_scheduleコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "エラーが発生しました。管理者に連絡してください。",
                    ephemeral=True
                )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


@bot.tree.command(name="sync_commands", description="コマンドを手動で同期（コマンドが表示されない場合に使用）")
async def sync_commands_cmd(interaction: discord.Interaction):
    """コマンドを手動で同期"""
    try:
        await interaction.response.defer(ephemeral=True)
        
        # 先に進行状況メッセージを送信
        await interaction.followup.send(
            "コマンド同期を開始します...",
            ephemeral=True
        )
        
        # サーバー限定同期のみを強制的に実行（即座に反映される）
        guild_id = config.get("guild_id")
        if guild_id and str(guild_id).strip():
            synced_commands = await sync_commands(force_guild_only=True)
        else:
            synced_commands = await sync_commands(force_guild_only=False)
        
        if synced_commands:
            command_list = "\n".join(f"- `/{cmd}`" for cmd in sorted(synced_commands))
            embed = discord.Embed(
                title="コマンド同期完了",
                description=f"{len(synced_commands)}個のコマンドを同期しました。",
                color=discord.Color.green()
            )
            embed.add_field(
                name="同期されたコマンド",
                value=command_list,
                inline=False
            )
            if guild_id and str(guild_id).strip():
                embed.set_footer(
                    text="サーバー限定同期を実行しました。Discordクライアントを再起動するか、数秒待ってからコマンドを確認してください。"
                )
            else:
                embed.set_footer(
                    text="グローバル同期を実行しました。反映には最大1時間かかる場合があります。"
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "コマンドの同期に失敗しました。ログを確認してください。",
                ephemeral=True
            )
    except Exception as e:
        print(f"sync_commandsコマンドでエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        try:
            await interaction.followup.send(
                "エラーが発生しました。管理者に連絡してください。",
                ephemeral=True
            )
        except Exception as followup_error:
            print(f"エラーメッセージの送信に失敗しました: {followup_error}")


# Cloud Run用のHTTPサーバー（ヘルスチェック対応）
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        # ログを抑制（Discordボットのログと混在しないように）
        pass

def start_health_check_server(port=8080):
    """Cloud Run用のヘルスチェックサーバーを起動"""
    server = HTTPServer(('', port), HealthCheckHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[ヘルスチェック] HTTPサーバーをポート{port}で起動しました")


if __name__ == "__main__":
    # Cloud Run用のHTTPサーバーを起動（環境変数PORTが設定されている場合）
    port = int(os.environ.get('PORT', 0))
    if port > 0:
        start_health_check_server(port)
    
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Discordボット")
    parser.add_argument(
        "--test-send-time",
        type=str,
        help="テスト用の送信時刻を指定（HH:MM形式、例: 20:00）"
    )
    parser.add_argument(
        "--force-send",
        action="store_true",
        help="即座にメッセージを送信（テスト用）"
    )
    args = parser.parse_args()
    
    if not config.get("token"):
        print("エラー: config.jsonにトークンが設定されていません。")
    else:
        # テスト用の送信時刻が指定されている場合
        if args.test_send_time:
            try:
                hour, minute = map(int, args.test_send_time.split(":"))
                test_send_time = time(hour, minute)
                # スケジューラーの送信時刻を一時的に変更
                scheduler.send_time = test_send_time
                print(f"[テスト] 送信時刻を {args.test_send_time} に設定しました")
            except ValueError:
                print(f"エラー: 送信時刻の形式が正しくありません。HH:MM形式で指定してください（例: 20:00）")
                exit(1)
        
        # 即座に送信する場合（テスト用）
        if args.force_send:
            # グローバルフラグを設定（on_readyでチェック）
            # モジュールレベル変数なので直接参照可能
            globals()['force_send_flag'] = True
        
        bot.run(config["token"])

