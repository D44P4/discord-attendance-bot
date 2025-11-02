"""Discordボットメインファイル"""
import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from datetime import datetime
import pytz
from utils.scheduler import Scheduler
from utils.data_manager import DataManager
from utils.holidays import HolidayManager


# Botの設定を読み込み
def load_config():
    """設定ファイルを読み込む（環境変数優先）"""
    # 環境変数から読み込む（Railway等のクラウド環境向け）
    discord_token = os.environ.get("DISCORD_TOKEN")
    if discord_token:
        config = {
            "token": discord_token,
            "guild_id": os.environ.get("GUILD_ID", ""),
            "channel_id": os.environ.get("CHANNEL_ID", ""),
            "send_time": os.environ.get("SEND_TIME", "20:00"),
            "weekdays": json.loads(os.environ.get("WEEKDAYS", "[4,5]")),
            "send_before_holidays": os.environ.get("SEND_BEFORE_HOLIDAYS", "true").lower() == "true"
        }
        return config
    
    # 設定ファイルから読み込む（ローカル環境向け）
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
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


@bot.event
async def on_ready():
    """Bot起動時の処理"""
    print(f"{bot.user} がログインしました")
    
    # 少し待ってからコマンドを同期（Discord APIの準備を待つ）
    await asyncio.sleep(1)
    
    # スケジュールチェックタスクを開始
    if not scheduler_task.is_running():
        scheduler_task.start()
    
    # コマンドを同期（サーバー限定とグローバルの両方を試す）
    try:
        guild_id = config.get("guild_id")
        
        # まずサーバー限定で同期（即座に反映）
        if guild_id and str(guild_id).strip():
            try:
                guild = discord.Object(id=int(guild_id))
                synced_guild = await bot.tree.sync(guild=guild)
                print(f"サーバー限定で {len(synced_guild)} 個のコマンドを同期しました: {[cmd.name for cmd in synced_guild]}")
            except (ValueError, TypeError) as e:
                print(f"サーバー限定コマンドの同期をスキップしました（guild_idが無効）: {e}")
        
        # グローバルでも同期（反映に時間がかかるが、どのサーバーでも使える）
        synced_global = await bot.tree.sync()
        print(f"グローバルで {len(synced_global)} 個のコマンドを同期しました: {[cmd.name for cmd in synced_global]}")
        
    except Exception as e:
        print(f"コマンドの同期に失敗しました: {e}")
        import traceback
        traceback.print_exc()


async def check_and_send_summary():
    """22時に集計結果を送信するチェック"""
    now = datetime.now(pytz.timezone("Asia/Tokyo"))
    
    # 22時になったかチェック
    if now.hour == 22 and now.minute == 0:
        date_str = now.strftime("%Y-%m-%d")
        
        # 今日メッセージを送信したかチェック
        if date_str in sent_dates:
            if config.get("channel_id"):
                channel = bot.get_channel(int(config["channel_id"]))
                if channel:
                    summary = data_manager.get_summary(now)
                    
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
                            user_list.append(f"<@{user_id}>: {start_time} ～ {end_time}")
                        
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


@tasks.loop(minutes=1)
async def scheduler_task():
    """定期メッセージ送信タスク"""
    await scheduler.check_and_send()
    # 集計結果送信チェック（22時に実行）
    await check_and_send_summary()


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

async def scheduled_send_callback(date: datetime):
    """スケジュール送信コールバック"""
    print(f"[コールバック] メッセージ送信コールバックが呼ばれました: {date.strftime('%Y-%m-%d %H:%M:%S')}")
    if config.get("channel_id"):
        channel = bot.get_channel(int(config["channel_id"]))
        if channel:
            print(f"[コールバック] チャンネルが見つかりました: {channel.name}")
            await send_question_message(channel, date)
            # 送信した日付を記録（集計結果送信用）
            date_str = date.strftime("%Y-%m-%d")
            sent_dates.add(date_str)
            print(f"[コールバック] メッセージを送信しました。送信日付を記録: {date_str}")
        else:
            print(f"[コールバック] エラー: チャンネルが見つかりません。channel_id={config.get('channel_id')}")
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
        """時刻選択オプションを作成（30分単位、降順）"""
        options = []
        # 30分単位の選択肢（23:30～0:00まで降順、全48個）
        # DiscordのSelectは25個までなので、開始時刻と終了時刻で範囲を分ける
        all_options = []
        for hour in range(23, -1, -1):  # 23時から0時まで降順
            for minute in [30, 0]:  # 30分、0分の順（降順）
                time_str = f"{hour:02d}:{minute:02d}"
                all_options.append(
                    discord.SelectOption(
                        label=time_str,
                        value=time_str,
                        description=f"{time_str}に設定"
                    )
                )
        
        # 開始時刻用: 23:30～12:00（25個）
        # 終了時刻用: 11:30～0:00（23個、25個以内）
        if select_type == "start":
            return all_options[:25]  # 23:30～12:00
        else:  # end
            return all_options[25:]  # 11:30～0:00
    
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
            content=f"参加可能時間帯を選択してください\n\n開始時刻: {self.start_time or '未選択'}\n終了時刻: {self.end_time or '未選択'}",
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
            message = f"回答を記録しました。\n参加可能時間: {self.start_time} ～ {self.end_time}"
        elif self.start_time:
            message = f"回答を記録しました。\n参加可能開始時刻: {self.start_time}"
        else:
            message = f"回答を記録しました。\n参加可能終了時刻: {self.end_time}"
        
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
        allowed_channel_id = config.get("channel_id")
        if allowed_channel_id and str(interaction.channel.id) != str(allowed_channel_id):
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
        except:
            await interaction.followup.send(
                "エラーが発生しました。管理者に連絡してください。",
                ephemeral=True
            )


@bot.tree.command(name="show_summary", description="集計結果を表示")
async def show_summary(interaction: discord.Interaction):
    """集計結果を表示"""
    # 指定されたチャンネルでのみコマンドを実行可能
    allowed_channel_id = config.get("channel_id")
    if allowed_channel_id and str(interaction.channel.id) != str(allowed_channel_id):
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
            user_list.append(f"<@{user_id}>: {start_time} ～ {end_time}")
        
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
    
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not config.get("token"):
        print("エラー: config.jsonにトークンが設定されていません。")
    else:
        bot.run(config["token"])

