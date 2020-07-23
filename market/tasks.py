from django.conf import settings
from django.utils import timezone

from elk.celery import app as celery
from market.models import Class


@celery.task
def notify_subscriptions_not_used():
    for i in Class.objects.filter(is_fully_used=False).filter(
        subscription__not_used_notification_sent_to_student=False).filter(
        timeline__end__lte=timezone.now() - settings.SUBSCRIPTION_NOT_USED):
        i.subscription.not_used_notification(last_used=i.buy_date)
