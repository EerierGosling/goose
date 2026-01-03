import os
from unittest import result
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import re
import requests

load_dotenv()

channel_id = os.environ.get("CHANNEL_ID")
user_id = os.environ.get("USER_ID")
canvas = os.environ.get("CANVAS")

morning_reminder_job = None
# evening_reminder_job = None

morning_presence_job = None

morning_thread_ts = None
evening_thread_ts = None

online = False

app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

def check_canvas_progress():

    try:
        file_url = app.client.files_info(file=canvas)["file"]["url_private_download"]

        headers = {
            "Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"
        }
        content = requests.get(file_url, headers=headers).text

        checked = len(re.findall(r"<li[^>]*class='checked'[^>]*>", content))
        unchecked = len(re.findall(r"<li[^>]*class=''[^>]*>", content))
        
        total = checked + unchecked
        
        return checked, unchecked, total
        
    except Exception as e:
        print(f"error reading canvas: {e}")
        return 0, 0, 0

def check_presence():
    global online

    try:
        result = app.client.users_getPresence(user=user_id)
        online = result['presence'] == 'active'
        
    except Exception as e:
        print(f"error w/ presence: {e}")


@app.event("reaction_added")
def handle_reaction_added(event, say):
    global morning_reminder_job
    # global evening_reminder_job
    global morning_thread_ts
    global evening_thread_ts
    global morning_presence_job
    global online

    if event["user"] != user_id or event["reaction"] != "white_check_mark" or not event.get("item", {}).get("ts"):
        return
    
    if event["item"]["ts"] == morning_thread_ts:
        morning_thread_ts = None

        if morning_reminder_job:
            morning_reminder_job.remove()
            morning_reminder_job = None

        if morning_presence_job:
            morning_presence_job.remove()
            morning_presence_job = None
            online = False

        say(channel=channel_id, thread_ts=morning_thread_ts, text=f"thanks! good luck! :yay:")

    elif event["item"]["ts"] == evening_thread_ts:
        # if evening_reminder_job:
        #     evening_reminder_job.remove()
        #     evening_reminder_job = None
        say(channel=channel_id, thread_ts=evening_thread_ts, text=f"thanks! hope today was productive :D")
        evening_thread_ts = None

        num_done = check_canvas_progress()

        app.client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> got done {num_done[0]} of {num_done[2]} goals for today! :D (<https://hackclub.enterprise.slack.com/docs/T0266FRGM/F0A6CJSMTD1|canvas>)",
        )

def morning_start():
    global morning_reminder_job
    global morning_thread_ts
    global morning_presence_job
    global online

    try:
        response = app.client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> what are your goals for today? :duck-plead:"
        )

        morning_thread_ts = response.get("ts")
        if not morning_thread_ts:
            return

        if morning_reminder_job:
            morning_reminder_job.remove()
            morning_reminder_job = None
        if morning_presence_job:
            morning_presence_job.remove()
            morning_presence_job = None
            online = False
        
        morning_reminder_job = job_scheduler.add_job(morning_reminder, 'interval', hours=1)
        morning_presence_job = job_scheduler.add_job(check_presence, 'interval', minutes=2)

    except Exception as e:
        print(f"error sending morning msg: {e}")

def evening_start():
    # global evening_reminder_job
    global evening_thread_ts

    try:
        response = app.client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}>! what did you get done today?"
        )

        evening_thread_ts = response.get("ts")
        if not evening_thread_ts:
            return

        # if evening_reminder_job:
        #     evening_reminder_job.remove()
        #     evening_reminder_job = None
        # evening_reminder_job = job_scheduler.add_job(evening_reminder, 'interval', hours=1)

    except Exception as e:
        print(f"error sending evening msg: {e}")

def morning_reminder():
    global morning_reminder_job
    global morning_presence_job
    global online
    global morning_thread_ts

    try:
        current_time = datetime.now(pytz.timezone('America/New_York'))
        if current_time.hour >= 23: # 5 pm
            morning_thread_ts = None

            if morning_reminder_job:
                morning_reminder_job.remove()
                morning_reminder_job = None
            if morning_presence_job:
                morning_presence_job.remove()
                morning_presence_job = None
                online = False

            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=morning_thread_ts,
                text="i'll stop reminding you now... but please don't forget tomorrow!",
            )
            return

        if not online:
            return
        
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=morning_thread_ts,
            text=f"<@{user_id}> please update your goals for today! :blobhaj_knife:",
        )
    except Exception as e:
        print(f"error sending hourly msg: {e}")


job_scheduler = BackgroundScheduler(timezone=pytz.timezone('America/New_York'))
morning_start_job = job_scheduler.add_job(morning_start, 'cron', hour=7, minute=0)
evening_start_job = job_scheduler.add_job(evening_start, 'cron', hour=20, minute=0)
job_scheduler.start()
        
if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()