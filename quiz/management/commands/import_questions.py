from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from quiz.importer import QuestionFormatError, import_text, parse, resolve_subject
from quiz.models import Question, Subject


class Command(BaseCommand):
    help = "Savollarni txt fayl(lar)dan import qiladi. Format: quiz/importer.py boshidagi izohga qarang."

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help='txt fayl(lar) yoki papka')
        parser.add_argument('--subject', help="Faylda 'FAN:' qatori bo'lmasa: english | informatics | history")
        parser.add_argument('--dry-run', action='store_true', help='Faqat tekshirish, bazaga yozmaslik')

    def handle(self, *args, **options):
        subject = resolve_subject(options['subject']) if options['subject'] else None
        files = []
        for raw in options['paths']:
            path = Path(raw)
            if path.is_dir():
                files.extend(sorted(path.glob('*.txt')))
            elif path.is_file():
                files.append(path)
            else:
                raise CommandError(f'Topilmadi: {path}')

        for path in files:
            text = path.read_text(encoding='utf-8')
            try:
                if options['dry_run']:
                    result = parse(text, subject)
                    self.stdout.write(f'{path}: {len(result.questions)} ta savol, xato yo\'q ({result.subject})')
                    continue
                result, created, updated = import_text(text, subject)
            except QuestionFormatError as exc:
                raise CommandError(f'{path}:\n{exc}')
            self.stdout.write(self.style.SUCCESS(
                f'{path}: {result.subject} — {created} ta yangi, {updated} ta yangilandi'
            ))

        self.stdout.write('\nBazadagi savollar:')
        for s in Subject:
            self.stdout.write(f'  {s.label}: {Question.objects.filter(subject=s).count()}')
