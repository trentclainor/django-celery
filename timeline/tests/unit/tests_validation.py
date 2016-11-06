from django.core.exceptions import ValidationError
from django.test import override_settings
from mixer.backend.django import mixer

from elk.utils.testing import TestCase, create_teacher
from extevents.models import ExternalEvent
from lessons import models as lessons
from teachers.models import Absence, WorkingHours
from timeline.models import Entry as TimelineEntry


class EntryValidationTestCase(TestCase):
    def setUp(self):
        self.teacher = create_teacher()
        self.lesson = mixer.blend(lessons.OrdinaryLesson, teacher=self.teacher)

        self.big_entry = mixer.blend(
            TimelineEntry,
            teacher=self.teacher,
            start=self.tzdatetime(2016, 1, 2, 18, 0),
            end=self.tzdatetime(2016, 1, 3, 12, 0),
        )


class TestOverlapValidation(EntryValidationTestCase):
    def test_overlap(self):
        """
        Create two entries — one overlapping with the big_entry, and one — not
        """
        overlapping_entry = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2016, 1, 3, 4, 0),
            end=self.tzdatetime(2016, 1, 3, 4, 30),
        )
        self.assertTrue(overlapping_entry.is_overlapping())

        non_overlapping_entry = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2016, 1, 3, 12, 0),
            end=self.tzdatetime(2016, 1, 3, 12, 30),
        )
        self.assertFalse(non_overlapping_entry.is_overlapping())

        def test_overlapping_with_different_teacher(self):
            """
            Check, if it's pohuy, that an entry overlapes entry of the other teacher
            """
            other_teacher = create_teacher()
            test_entry = TimelineEntry(
                teacher=other_teacher,
                start=self.tzdatetime(2016, 1, 3, 4, 0),
                end=self.tzdatetime(2016, 1, 3, 4, 30),
            )
            self.assertFalse(test_entry.is_overlapping())

        def test_two_equal_entries(self):
            """
            Two equal entries should overlap each other
            """
            first_entry = mixer.blend(
                TimelineEntry,
                teacher=self.teacher,
                start=self.tzdatetime(2016, 1, 3, 4, 0),
                end=self.tzdatetime(2016, 1, 3, 4, 30),
            )
            first_entry.save()

            second_entry = TimelineEntry(
                teacher=self.teacher,
                start=self.tzdatetime(2016, 1, 3, 4, 0),
                end=self.tzdatetime(2016, 1, 3, 4, 30),
            )
            self.assertTrue(second_entry.is_overlapping())

        def test_cant_save_due_to_overlap(self):
            """
            We should not have posibillity to save a timeline entry, that can not
            be created
            """
            overlapping_entry = TimelineEntry(
                teacher=self.teacher,
                lesson=self.lesson,
                start=self.tzdatetime(2016, 1, 3, 4, 0),
                end=self.tzdatetime(2016, 1, 3, 4, 30),
                allow_overlap=False,  # excplicitly say, that entry can't overlap other ones
            )
            with self.assertRaises(ValidationError):
                overlapping_entry.clean()

        def test_double_save_an_entry_that_does_not_allow_overlapping(self):
            """
            Create an entry that does not allow overlapping and the save it again
            """
            entry = TimelineEntry(
                teacher=self.teacher,
                lesson=self.lesson,
                start=self.tzdatetime(2016, 1, 10, 4, 0),
                end=self.tzdatetime(2016, 1, 10, 4, 30),
                allow_overlap=False
            )
            entry.clean()
            entry.save()

            entry.start = self.tzdatetime(2016, 1, 10, 4, 1)  # change random parameter
            entry.clean()
            entry.save()
            self.assertIsNotNone(entry)  # should not throw anything


@override_settings(TIME_ZONE='UTC')
class TestWorkingHoursValiation(EntryValidationTestCase):
    def test_working_hours(self):
        mixer.blend(WorkingHours, teacher=self.teacher, start='12:00', end='13:00', weekday=0)
        entry_besides_hours = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 4, 0),
            end=self.tzdatetime(2032, 5, 3, 4, 30),
        )
        self.assertFalse(entry_besides_hours.is_fitting_working_hours())

        entry_within_hours = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 12, 30),
            end=self.tzdatetime(2032, 5, 3, 13, 0),
        )
        self.assertTrue(entry_within_hours.is_fitting_working_hours())

    def test_working_hours_multidate(self):
        """
        Test checking working hours when lesson starts in one day, and ends on
        another. This will be frequent situations, because our teachers are
        in different timezones.
        """
        mixer.blend(WorkingHours, teacher=self.teacher, start='23:00', end='23:59', weekday=0)
        mixer.blend(WorkingHours, teacher=self.teacher, start='00:00', end='02:00', weekday=1)

        entry_besides_hours = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 22, 0),  # does not fit
            end=self.tzdatetime(2032, 5, 4, 0, 30)
        )
        self.assertFalse(entry_besides_hours.is_fitting_working_hours())

        entry_besides_hours.start = self.tzdatetime(2032, 5, 3, 22, 30)  # does fit
        entry_besides_hours.end = self.tzdatetime(2016, 7, 26, 2, 30)    # does not fit

        self.assertFalse(entry_besides_hours.is_fitting_working_hours())

        entry_within_hours = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 23, 30),
            end=self.tzdatetime(2032, 5, 4, 0, 30)
        )
        self.assertTrue(entry_within_hours.is_fitting_working_hours())

    def test_working_hours_nonexistant(self):
        entry = TimelineEntry(
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 22, 0),  # does not fit
            end=self.tzdatetime(2032, 5, 3, 22, 30),
        )
        self.assertFalse(entry.is_fitting_working_hours())  # should not throw anything

    def test_cant_save_due_to_not_fitting_working_hours(self):
        """
        Create an entry that does not fit into teachers working hours
        """
        entry = TimelineEntry(
            teacher=self.teacher,
            lesson=self.lesson,
            start=self.tzdatetime(2032, 5, 3, 13, 30),  # monday
            end=self.tzdatetime(2032, 5, 3, 14, 0),
            allow_besides_working_hours=False
        )
        with self.assertRaises(ValidationError, msg='Entry does not fit teachers working hours'):
            entry.clean()

        mixer.blend(WorkingHours, teacher=self.teacher, weekday=0, start='13:00', end='15:00')  # monday
        entry.save()
        self.assertIsNotNone(entry.pk)  # should be saved now


class TestTeacherPresenceValidation(EntryValidationTestCase):
    def setUp(self):
        super().setUp()
        self.entry = TimelineEntry(
            teacher=self.teacher,
            lesson=self.lesson,
            start=self.tzdatetime(2032, 5, 3, 13, 30),
            end=self.tzdatetime(2032, 5, 3, 14, 0),
        )

    def test_teacher_available_true(self):
        self.assertTrue(self.entry.teacher_is_present())

    def test_teacher_available_true_becuase_of_vacation_is_for_another_teacher(self):
        vacation = Absence(
            type='vacation',
            teacher=create_teacher(),  # some other teacher, not the one owning self.entry
            start=self.tzdatetime(2032, 5, 2, 0, 0),
            end=self.tzdatetime(2032, 2, 5, 23, 59),
        )
        vacation.save()

        self.assertTrue(self.entry.teacher_is_present())

    def test_teacher_available_false(self):
        vacation = Absence(
            type='vacation',
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 2, 00, 00),
            end=self.tzdatetime(2032, 5, 5, 23, 59),
        )
        vacation.save()
        self.assertFalse(self.entry.teacher_is_present())

    def test_teacher_available_false_due_to_vacation_starts_inside_of_period(self):
        vacation = Absence(
            type='vacation',
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 3, 13, 45),
            end=self.tzdatetime(2032, 5, 5, 23, 59),
        )
        vacation.save()
        self.assertFalse(self.entry.teacher_is_present())

    def test_teacher_available_false_due_to_vacation_ends_inside_of_period(self):
        vacation = Absence(
            type='vacation',
            teacher=self.teacher,
            start=self.tzdatetime(2032, 5, 2, 0, 0),
            end=self.tzdatetime(2032, 5, 3, 13, 45),
        )
        vacation.save()
        self.assertFalse(self.entry.teacher_is_present())

    def test_cant_save_due_to_teacher_absence(self):
        entry = TimelineEntry(
            teacher=self.teacher,
            lesson=self.lesson,
            start=self.tzdatetime(2016, 5, 3, 13, 30),
            end=self.tzdatetime(2016, 5, 3, 14, 00),
        )
        vacation = Absence(
            type='vacation',
            teacher=self.teacher,
            start=self.tzdatetime(2016, 5, 2, 00, 00),
            end=self.tzdatetime(2016, 5, 5, 23, 59),
        )
        vacation.save()
        with self.assertRaises(ValidationError):
            entry.clean()


class TestExternalEventValidation(EntryValidationTestCase):
    def setUp(self):
        super().setUp()
        self.entry = TimelineEntry(
            teacher=self.teacher,
            lesson=self.lesson,
            start=self.tzdatetime(2032, 5, 3, 13, 30),
            end=self.tzdatetime(2032, 5, 3, 14, 00),
        )

    def test_cant_save_due_to_teacher_has_events(self):
        entry = TimelineEntry(
            teacher=self.teacher,
            lesson=self.lesson,
            start=self.tzdatetime(2016, 5, 3, 13, 30),
            end=self.tzdatetime(2016, 5, 3, 14, 00),
        )
        mixer.blend(
            ExternalEvent,
            teacher=self.teacher,
            start=self.tzdatetime(2016, 5, 2, 00, 00),
            end=self.tzdatetime(2016, 5, 5, 23, 59),
        )
        with self.assertRaises(ValidationError):
            entry.clean()
