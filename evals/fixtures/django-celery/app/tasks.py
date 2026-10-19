from celery import shared_task
from django.contrib.sessions.models import Session
from django.utils import timezone


@shared_task
def cleanup_sessions():
    deleted, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
    return deleted
