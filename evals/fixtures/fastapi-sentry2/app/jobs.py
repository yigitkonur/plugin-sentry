from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def nightly_cleanup() -> None:
    print("cleaning up")


scheduler.add_job(nightly_cleanup, "cron", hour=3)
