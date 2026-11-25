"""Savollarni txt fayldan import qilish.

Fayl formati (UTF-8):

    FAN: english                 <- english | informatics | history (yoki ingliz, informatika, tarix)

    1. Savol matni               <- raqam ixtiyoriy, savol bir necha qatordan iborat bo'lishi mumkin
    birinchi variant
    # to'g'ri variant            <- to'g'ri javob '#' bilan boshlanadi
    uchinchi variant
    to'rtinchi variant

    MATN:                        <- keyingi savollarga umumiy matn (masalan, reading passage)
    Matnning o'zi...

    5. Matnga oid savol
    ...

    MATN TUGADI                  <- shundan keyingi savollarga matn qo'shilmaydi

Savollar bo'sh qator bilan ajratiladi. Har savolda oxirgi 4 qator — variantlar,
ulardan aynan bittasi '#' bilan belgilangan bo'lishi kerak.
"""

import re
from dataclasses import dataclass, field

from django.db import transaction

from .models import Question, Subject

SUBJECT_ALIASES = {
    'english': Subject.ENGLISH,
    'ingliz': Subject.ENGLISH,
    'ingliz tili': Subject.ENGLISH,
    'informatics': Subject.INFORMATICS,
    'informatika': Subject.INFORMATICS,
    'history': Subject.HISTORY,
    'tarix': Subject.HISTORY,
}
LETTERS = 'ABCD'
NUMBER_RE = re.compile(r'^\d+\s*[.)]\s+')


class QuestionFormatError(Exception):
    pass


@dataclass
class ParsedQuestion:
    line: int
    text: str
    options: list
    correct: str
    context: str = ''


@dataclass
class ParseResult:
    subject: str
    questions: list = field(default_factory=list)


def resolve_subject(value):
    subject = SUBJECT_ALIASES.get(value.strip().lower())
    if not subject:
        raise QuestionFormatError(f"Noma'lum fan: {value!r}. Mumkin: english, informatics, history")
    return subject


def _blocks(text):
    """Bo'sh qatorlar bilan ajratilgan bloklar: [(boshlanish_qatori, [qatorlar])]."""
    blocks, current, start = [], [], 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip().replace('﻿', '')
        if line:
            if not current:
                start = number
            current.append(line)
        elif current:
            blocks.append((start, current))
            current = []
    if current:
        blocks.append((start, current))
    return blocks


def parse(text, subject=None):
    errors = []
    context = ''
    result = ParseResult(subject=subject)

    for start, lines in _blocks(text):
        head = lines[0]
        upper = head.upper()

        if upper.startswith('FAN:'):
            result.subject = resolve_subject(head[4:])
            continue
        if upper == 'MATN TUGADI':
            context = ''
            continue
        if upper.startswith('MATN:'):
            context = '\n'.join(([head[5:].strip()] if head[5:].strip() else []) + lines[1:])
            continue

        if len(lines) < 5:
            errors.append(f'{start}-qator: savol va 4 ta variant bo\'lishi kerak, {len(lines)} ta qator topildi')
            continue

        question_lines, option_lines = lines[:-4], lines[-4:]
        question_lines[0] = NUMBER_RE.sub('', question_lines[0])
        marked = [i for i, opt in enumerate(option_lines) if opt.startswith('#')]
        if len(marked) != 1:
            errors.append(
                f"{start}-qator: aynan bitta to'g'ri javob '#' bilan belgilanishi kerak, {len(marked)} ta topildi"
            )
            continue

        options = [opt.lstrip('#').strip() for opt in option_lines]
        if any(not opt for opt in options):
            errors.append(f"{start}-qator: bo'sh variant bor")
            continue

        result.questions.append(ParsedQuestion(
            line=start,
            text='\n'.join(question_lines).strip(),
            options=options,
            correct=LETTERS[marked[0]],
            context=context,
        ))

    if not result.subject:
        errors.append("Fan aniqlanmadi: faylga 'FAN: english' kabi qator qo'shing")
    if errors:
        raise QuestionFormatError('\n'.join(errors))
    return result


@transaction.atomic
def save(result):
    """Savollarni bazaga yozadi. Matni bir xil savol bo'lsa yangilaydi (dublikat qilmaydi)."""
    created = updated = 0
    for q in result.questions:
        values = {
            'option_a': q.options[0],
            'option_b': q.options[1],
            'option_c': q.options[2],
            'option_d': q.options[3],
            'correct': q.correct,
        }
        _, is_new = Question.objects.update_or_create(
            subject=result.subject,
            text=q.text,
            context=q.context,
            defaults=values,
        )
        if is_new:
            created += 1
        else:
            updated += 1
    return created, updated


def import_text(text, subject=None):
    result = parse(text, subject)
    created, updated = save(result)
    return result, created, updated
