import random
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Answer, Attempt, Option, Question, Subject

SESSION_KEY = 'attempt_id'
VALID_OPTIONS = set(Option.values)
# Vaqt tugagach, avtomatik yuborilgan forma uchun kichik zaxira (tarmoq kechikishi)
GRACE = timedelta(seconds=15)


def _current_attempt(request):
    attempt_id = request.session.get(SESSION_KEY)
    if not attempt_id:
        return None
    return Attempt.objects.filter(pk=attempt_id).first()


def _pick_questions():
    """Har fandan belgilangan sonda savol oladi va ularni aralashtiradi."""
    picked = []
    for subject, count in settings.TEST_SUBJECT_COUNTS.items():
        ids = list(Question.objects.filter(subject=subject).values_list('id', flat=True))
        if len(ids) < count:
            return None
        picked.extend(random.sample(ids, count))
    random.shuffle(picked)
    return picked


def start(request):
    attempt = _current_attempt(request)
    if attempt:
        return redirect('quiz:result' if attempt.is_finished else 'quiz:test')

    error = None
    full_name = ''
    if request.method == 'POST':
        full_name = ' '.join(request.POST.get('full_name', '').split())
        if len(full_name) < 3:
            error = 'Iltimos, ism va familiyangizni to\'liq kiriting.'
        else:
            question_ids = _pick_questions()
            if question_ids is None:
                error = 'Bazada savollar yetarli emas. Administratorga murojaat qiling.'
            else:
                with transaction.atomic():
                    attempt = Attempt.objects.create(full_name=full_name)
                    Answer.objects.bulk_create([
                        Answer(attempt=attempt, question_id=qid, order=i)
                        for i, qid in enumerate(question_ids, start=1)
                    ])
                request.session[SESSION_KEY] = attempt.pk
                return redirect('quiz:test')

    counts = [(Subject(key).label, n) for key, n in settings.TEST_SUBJECT_COUNTS.items()]
    return render(request, 'quiz/start.html', {
        'error': error,
        'full_name': full_name,
        'counts': counts,
        'total': sum(n for _, n in counts),
        'minutes': settings.TEST_DURATION_MINUTES,
    })


def test(request):
    attempt = _current_attempt(request)
    if not attempt:
        return redirect('quiz:start')
    if attempt.is_expired:
        attempt.finish()
    if attempt.is_finished:
        return redirect('quiz:result')

    answers = list(attempt.answers.select_related('question'))
    return render(request, 'quiz/test.html', {
        'attempt': attempt,
        'answers': answers,
        'answered_count': sum(1 for a in answers if a.selected),
        'remaining': attempt.remaining_seconds,
    })


@require_POST
def save_answer(request):
    attempt = _current_attempt(request)
    if not attempt or attempt.is_finished:
        return JsonResponse({'ok': False, 'finished': True}, status=403)
    if attempt.is_expired:
        attempt.finish()
        return JsonResponse({'ok': False, 'finished': True}, status=403)

    answer_id = request.POST.get('answer')
    selected = request.POST.get('selected', '')
    if selected not in VALID_OPTIONS:
        return JsonResponse({'ok': False}, status=400)
    updated = attempt.answers.filter(pk=answer_id).update(selected=selected)
    return JsonResponse({'ok': bool(updated)})


@require_POST
def submit(request):
    attempt = _current_attempt(request)
    if not attempt:
        return redirect('quiz:start')

    if not attempt.is_finished and timezone.now() <= attempt.deadline + GRACE:
        answers = attempt.answers.all()
        changed = []
        for answer in answers:
            value = request.POST.get(f'q{answer.pk}', '')
            if value in VALID_OPTIONS and value != answer.selected:
                answer.selected = value
                changed.append(answer)
        if changed:
            Answer.objects.bulk_update(changed, ['selected'])
    attempt.finish()
    return redirect('quiz:result')


def result(request):
    attempt = _current_attempt(request)
    if not attempt:
        return redirect('quiz:start')
    if attempt.is_expired:
        attempt.finish()
    if not attempt.is_finished:
        return redirect('quiz:test')
    return render(request, 'quiz/result.html', {
        'attempt': attempt,
        'total': attempt.total,
    })


@require_POST
def restart(request):
    request.session.pop(SESSION_KEY, None)
    return redirect('quiz:start')
