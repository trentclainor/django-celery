from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from freezegun import freeze_time
from mixer.backend.django import mixer

from elk.utils.testing import TestCase, create_customer, create_teacher
from market.models import Subscription
from market.tasks import notify_subscriptions_not_used
from products.models import Product1


@freeze_time('2032-12-05 12:00')
class TestNotUsedTask(TestCase):
    fixtures = ('products', 'lessons')

    @classmethod
    def setUpTestData(cls):
        cls.product = Product1.objects.get(pk=1)
        cls.product.duration = timedelta(days=5)
        cls.product.save()

        cls.customer = create_customer()

    def setUp(self):
        self.s = Subscription(
            customer=self.customer,
            product=self.product,
            buy_price=150
        )
        self.s.save()

    @patch('market.models.signals.class_scheduled.send')
    def _schedule(self, c, date, *args):
        c.timeline = mixer.blend(
            'timeline.Entry',
            lesson_type=c.lesson_type,
            teacher=create_teacher(),
            start=date,
            end=date + timedelta(hours=1),
        )
        c.save()

    def test_update_first_lesson_date(self):
        with freeze_time('2032-12-05 12:00'):
            first_class = self.s.classes.first()

            self._schedule(first_class, self.tzdatetime(2032, 12, 5, 13, 33))

            self.s.first_lesson_date = None  # set to None in case of first_class has set it up manualy — we check the subscription, not the class logic

            self.s.update_first_lesson_date()
            self.s.refresh_from_db()
            self.assertEqual(self.s.first_lesson_date, self.tzdatetime(2032, 12, 5, 13, 33))

        with freeze_time('2032-12-15 15:46'):
            notify_subscriptions_not_used()

        self.s.refresh_from_db()
        self.assertTrue(self.s.not_used_notification_sent_to_student)

        self.assertEqual(len(mail.outbox), 1)

        out_emails = [outbox.to[0] for outbox in mail.outbox]

        self.assertIn(self.customer.user.email, out_emails)
