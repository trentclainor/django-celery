from django.dispatch import Signal, receiver

from elk.logging import write_admin_log_entry
from mailer.owl import Owl


class_scheduled = Signal(providing_args=['instance'])  # class is just scheduled
class_cancelled = Signal(providing_args=['instance', 'src'])  # class is just cancelled
subscription_deactivated = Signal(providing_args=['user', 'instance'])
subscription_not_used = Signal(providing_args=['user', 'last_used'])


@receiver(subscription_deactivated, dispatch_uid='write_log_entry')
def write_log_entry_about_subscription_deactivation(sender, **kwargs):
    if kwargs['user'] is not None:
        """
        Anonymous user meens that someone has called :model:`market.Subscription`
        deactivate() method without a refernce to user.

        In most cases this is emitted by :model:`market.Subscription` delete(),
        method called from django-admin, so we can safely ignore it.
        """
        write_admin_log_entry(kwargs['user'], kwargs['instance'], msg='Subscription deactivated')


@receiver(subscription_not_used, dispatch_uid='notify_student_subscription_not_used')
def notify_student_about_subscription_not_used(sender, **kwargs):
    c = kwargs['instance']
    owl = Owl(
        template='mail/class/student/not_used.html',
        ctx={
            'c': c,
            'last_used': kwargs['last_used']
        },
        to=[c.customer.user.email],
        timezone=c.customer.timezone,
    )
    owl.send()


@receiver(class_scheduled, dispatch_uid='notify_student_class_scheduled')
def notify_student_class_scheduled(sender, **kwargs):
    c = kwargs['instance']
    owl = Owl(
        template='mail/class/student/scheduled.html',
        ctx={
            'c': c,
        },
        to=[c.customer.user.email],
        timezone=c.customer.timezone,
    )
    owl.attach('elk-class.ics', content=c.timeline.as_ical(for_whom='customer'))
    owl.send()


@receiver(class_scheduled, dispatch_uid='notify_teacher_class_scheduled')
def notify_teacher_class_scheduled(sender, **kwargs):
    c = kwargs['instance']
    owl = Owl(
        template='mail/class/teacher/scheduled.html',
        ctx={
            'c': c,
        },
        to=[c.timeline.teacher.user.email],
        timezone=c.timeline.teacher.user.crm.timezone,
    )
    owl.attach('elk-class.ics', content=c.timeline.as_ical(for_whom='teacher'))
    owl.send()


@receiver(class_cancelled, dispatch_uid='notify_student_class_is_cancelled')
def notify_student_class_is_cancelled(sender, **kwargs):
    c = kwargs['instance']
    owl = Owl(
        template='mail/class/student/cancelled.html',
        ctx={
            'c': c,
            'src': kwargs['src'],
        },
        to=[c.customer.user.email],
        timezone=c.customer.timezone,
    )
    owl.send()


@receiver(class_cancelled, dispatch_uid='notify_teacher_class_is_cancelled')
def notify_teacher_class_is_cancelled(sender, **kwargs):
    c = kwargs['instance']
    owl = Owl(
        template='mail/class/teacher/cancelled.html',
        ctx={
            'c': c,
            'src': kwargs['src'],
        },
        to=[c.timeline.teacher.user.email],
        timezone=c.timeline.teacher.user.crm.timezone,
    )
    owl.send()
