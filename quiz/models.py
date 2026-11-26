from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subject(models.TextChoices):
    ENGLISH = 'english', 'Ingliz tili'
    INFORMATICS = 'informatics', 'Informatika'
    HISTORY = 'history', 'Tarix'


class Option(models.TextChoices):
    A = 'A', 'A'
    B = 'B', 'B'
    C = 'C', 'C'
    D = 'D', 'D'


class Question(models.Model):
    subject = models.CharField('Fan', max_length=20, choices=Subject.choices)
    context = models.TextField('Umumiy matn', blank=True, help_text='Masalan, reading passage. Bir nechta savolga umumiy.')
    text = models.TextField('Savol')
    option_a = models.CharField('A variant', max_length=500)
    option_b = models.CharField('B variant', max_length=500)
    option_c = models.CharField('C variant', max_length=500)
    option_d = models.CharField('D variant', max_length=500)
    correct = models.CharField("To'g'ri javob", max_length=1, choices=Option.choices)

    class Meta:
        verbose_name = 'Savol'
        verbose_name_plural = 'Savollar'
        ordering = ['subject', 'id']

    def __str__(self):
        return f'[{self.get_subject_display()}] {self.text[:60]}'

    @property
    def options(self):
        return [
            ('A', self.option_a),
            ('B', self.option_b),
            ('C', self.option_c),
            ('D', self.option_d),
        ]


class Attempt(models.Model):
    full_name = models.CharField('Ism familiya', max_length=200)
    started_at = models.DateTimeField('Boshlangan', default=timezone.now)
    finished_at = models.DateTimeField('Tugagan', null=True, blank=True)
    is_finished = models.BooleanField('Tugallangan', default=False)
    score = models.PositiveSmallIntegerField('Ball', default=0)

    class Meta:
        verbose_name = 'Natija'
        verbose_name_plural = 'Natijalar'
        ordering = ['-score', 'finished_at']

    def __str__(self):
        return f'{self.full_name} — {self.score}'

    @property
    def deadline(self):
        return self.started_at + timedelta(minutes=settings.TEST_DURATION_MINUTES)

    @property
    def remaining_seconds(self):
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    @property
    def is_expired(self):
        return timezone.now() >= self.deadline

    @property
    def total(self):
        return self.answers.count()

    def subject_scores(self):
        """Fanlar bo'yicha natija: [(fan nomi, to'g'ri, jami), ...] sozlamadagi tartibda."""
        stats = {}
        for answer in self.answers.select_related('question'):
            row = stats.setdefault(answer.question.subject, [0, 0])
            row[1] += 1
            if answer.is_correct:
                row[0] += 1
        order = list(settings.TEST_SUBJECT_COUNTS) + [s for s in stats if s not in settings.TEST_SUBJECT_COUNTS]
        return [(Subject(s).label, *stats[s]) for s in order if s in stats]

    def finish(self):
        if self.is_finished:
            return
        correct = 0
        for answer in self.answers.select_related('question'):
            if answer.selected and answer.selected == answer.question.correct:
                correct += 1
        self.score = correct
        self.is_finished = True
        self.finished_at = min(timezone.now(), self.deadline)
        self.save(update_fields=['score', 'is_finished', 'finished_at'])

    @classmethod
    def finish_expired(cls):
        limit = timezone.now() - timedelta(minutes=settings.TEST_DURATION_MINUTES)
        for attempt in cls.objects.filter(is_finished=False, started_at__lte=limit):
            attempt.finish()


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='+')
    order = models.PositiveSmallIntegerField('Tartib raqami')
    selected = models.CharField('Tanlangan', max_length=1, choices=Option.choices, blank=True)

    class Meta:
        verbose_name = 'Javob'
        verbose_name_plural = 'Javoblar'
        ordering = ['order']
        unique_together = [('attempt', 'question'), ('attempt', 'order')]

    def __str__(self):
        return f'{self.order}. {self.selected or "-"}'

    @property
    def is_correct(self):
        return bool(self.selected) and self.selected == self.question.correct
