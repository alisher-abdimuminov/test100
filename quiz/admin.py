from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify

from .importer import QuestionFormatError, import_text
from .models import Answer, Attempt, Question, Subject


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(MultipleFileField, self).clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class ImportForm(forms.Form):
    files = MultipleFileField(
        label='TXT fayl(lar)',
        widget=MultipleFileInput(attrs={'accept': '.txt'}),
    )
    subject = forms.ChoiceField(
        label="Fan (faylda 'FAN:' qatori bo'lmasa)",
        choices=[('', '— fayldan olinsin —')] + Subject.choices,
        required=False,
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'short_text', 'correct')
    list_filter = ('subject',)
    search_fields = ('text',)
    change_list_template = 'admin/quiz/question/change_list.html'

    def get_urls(self):
        custom = [
            path(
                'import/',
                self.admin_site.admin_view(self.import_view),
                name='quiz_question_import',
            ),
        ]
        return custom + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            return redirect('admin:quiz_question_changelist')
        form = ImportForm(request.POST or None, request.FILES or None)
        if request.method == 'POST' and form.is_valid():
            subject = form.cleaned_data['subject'] or None
            for upload in request.FILES.getlist('files'):
                try:
                    text = upload.read().decode('utf-8-sig')
                    result, created, updated = import_text(text, subject)
                except UnicodeDecodeError:
                    messages.error(request, f'{upload.name}: fayl UTF-8 kodlashda emas')
                except QuestionFormatError as exc:
                    messages.error(request, f'{upload.name}: hech narsa saqlanmadi. ' + str(exc).replace('\n', '; '))
                else:
                    messages.success(
                        request,
                        f'{upload.name}: {Subject(result.subject).label} — {created} ta yangi, {updated} ta yangilandi',
                    )
            return redirect('admin:quiz_question_changelist')

        counts = [(s.label, Question.objects.filter(subject=s).count()) for s in Subject]
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Savollarni TXT fayldan yuklash',
            'form': form,
            'counts': counts,
        }
        return render(request, 'admin/quiz/question/import.html', context)

    @admin.display(description='Savol')
    def short_text(self, obj):
        return obj.text[:90]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    fields = ('order', 'question', 'selected', 'correct_option', 'status')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('question')

    @admin.display(description="To'g'ri")
    def correct_option(self, obj):
        return obj.question.correct

    @admin.display(description='Holat')
    def status(self, obj):
        if obj.is_correct:
            return format_html('<b style="color:#16a34a">{}</b>', "to'g'ri")
        return format_html('<b style="color:#dc2626">{}</b>', "noto'g'ri")


def build_result_txt(attempt):
    lines = [
        f'F.I.Sh: {attempt.full_name}',
        f'Ball: {attempt.score} / {attempt.total}',
        *[f'  {label}: {correct} / {total}' for label, correct, total in attempt.subject_scores()],
        f'Boshlangan: {timezone.localtime(attempt.started_at):%d.%m.%Y %H:%M:%S}',
        f'Tugagan: {timezone.localtime(attempt.finished_at):%d.%m.%Y %H:%M:%S}' if attempt.finished_at else 'Tugagan: -',
        '',
    ]
    for answer in attempt.answers.select_related('question'):
        correct = answer.question.correct
        if not answer.selected:
            lines.append(f"{answer.order} - (javob berilmagan, to'g'ri {correct})")
        elif answer.selected == correct:
            lines.append(f"{answer.order} {answer.selected} (to'g'ri)")
        else:
            lines.append(f"{answer.order} {answer.selected} (noto'g'ri, to'g'ri {correct})")
    return '\n'.join(lines) + '\n'


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('rank', 'full_name', 'score', 'started_at', 'finished_at', 'duration', 'download_link')
    list_display_links = ('full_name',)
    search_fields = ('full_name',)
    readonly_fields = ('full_name', 'score', 'started_at', 'finished_at', 'is_finished')
    ordering = ('-score', 'finished_at')
    inlines = [AnswerInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_finished=True)

    def changelist_view(self, request, extra_context=None):
        # Vaqti tugab, lekin yuborilmay qolgan testlarni yakunlaymiz
        Attempt.finish_expired()
        self._ranks = {
            pk: i for i, pk in enumerate(
                Attempt.objects.filter(is_finished=True)
                .order_by('-score', 'finished_at')
                .values_list('pk', flat=True),
                start=1,
            )
        }
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        custom = [
            path(
                '<int:pk>/download/',
                self.admin_site.admin_view(self.download_view),
                name='quiz_attempt_download',
            ),
        ]
        return custom + super().get_urls()

    def download_view(self, request, pk):
        attempt = get_object_or_404(Attempt, pk=pk, is_finished=True)
        filename = f'{slugify(attempt.full_name) or "natija"}_{attempt.pk}.txt'
        response = HttpResponse(build_result_txt(attempt), content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @admin.display(description='#')
    def rank(self, obj):
        return getattr(self, '_ranks', {}).get(obj.pk, '')

    @admin.display(description='Sarflangan vaqt')
    def duration(self, obj):
        if not obj.finished_at:
            return '-'
        seconds = int((obj.finished_at - obj.started_at).total_seconds())
        return f'{seconds // 60:02d}:{seconds % 60:02d}'

    @admin.display(description='Natija (txt)')
    def download_link(self, obj):
        url = reverse('admin:quiz_attempt_download', args=[obj.pk])
        return format_html('<a class="button" href="{}">Yuklab olish</a>', url)
