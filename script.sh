#!/usr/bin/env bash
# Test100 ni serverga deploy qilish.
#
# Ishlatish (serverda, loyiha papkasida):
#     sudo ./script.sh            # oddiy deploy / yangilash
#     sudo ./script.sh --import   # savollarni questions/ dan majburan qayta yuklash
#
# Savollar faqat baza bo'sh bo'lganda avtomatik yuklanadi (admin paneldagi
# o'zgarishlar ustiga yozilmasligi uchun).

set -euo pipefail

APP=test100
PROJECT_DIR=/home/ali/test100
DOMAIN=test100.samdpi.uz
NGINX_AVAILABLE=/etc/nginx/sites-available/$APP
NGINX_ENABLED=/etc/nginx/sites-enabled/$APP
SYSTEMD_DIR=/etc/systemd/system

FORCE_IMPORT=0
[[ "${1:-}" == "--import" ]] && FORCE_IMPORT=1

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mXato:\033[0m %s\n' "$*" >&2; exit 1; }

# --- Tekshiruvlar ---------------------------------------------------------
[[ $EUID -eq 0 ]] || fail "root sifatida ishga tushiring: sudo ./script.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[[ "$SCRIPT_DIR" == "$PROJECT_DIR" ]] \
    || fail "loyiha $PROJECT_DIR da bo'lishi kerak (systemd/nginx fayllarida shu yo'l yozilgan), hozir: $SCRIPT_DIR"
cd "$PROJECT_DIR"

for f in nginix.conf test100.service test100.socket; do
    [[ -f "$f" ]] || fail "$f topilmadi"
done

# Loyiha fayllari egasi (ali) nomidan uv va manage.py ishlatamiz
OWNER=$(stat -c '%U' "$PROJECT_DIR")
as_owner() { sudo -u "$OWNER" -H env PATH="$PATH" "$@"; }

UV=$(command -v uv || true)
[[ -z "$UV" && -x "/home/$OWNER/.local/bin/uv" ]] && UV="/home/$OWNER/.local/bin/uv"
[[ -z "$UV" && -x "/home/$OWNER/.cargo/bin/uv" ]] && UV="/home/$OWNER/.cargo/bin/uv"
[[ -n "$UV" ]] || fail "uv topilmadi. O'rnating: curl -LsSf https://astral.sh/uv/install.sh | sh"

command -v nginx >/dev/null || fail "nginx o'rnatilmagan"

# --- .env (faqat birinchi marta) -----------------------------------------
if [[ ! -f .env ]]; then
    info ".env yaratilmoqda"
    SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '\n/+=')
    cat > .env <<EOF
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=$SECRET
DJANGO_ALLOWED_HOSTS=$DOMAIN
EOF
    chown "$OWNER": .env
    chmod 600 .env
else
    info ".env mavjud — o'zgartirilmadi"
fi

# --- Python muhit va Django ----------------------------------------------
info "Bog'liqliklar o'rnatilmoqda (uv sync)"
as_owner "$UV" sync --frozen --no-dev

MANAGE=(as_owner "$PROJECT_DIR/.venv/bin/python" manage.py)

info "Migratsiyalar"
"${MANAGE[@]}" migrate --noinput

info "Statik fayllar (collectstatic)"
"${MANAGE[@]}" collectstatic --noinput --clear -v0

QUESTION_COUNT=$("${MANAGE[@]}" shell -v0 -c "from quiz.models import Question; print(Question.objects.count())" 2>/dev/null | tail -1)
if [[ $FORCE_IMPORT -eq 1 || "$QUESTION_COUNT" == "0" ]]; then
    info "Savollar yuklanmoqda (questions/)"
    "${MANAGE[@]}" import_questions questions/
else
    info "Bazada $QUESTION_COUNT ta savol bor — import o'tkazib yuborildi (majburlash: --import)"
fi

# nginx (www-data) /home/ali/test100/static ga yetib borishi uchun papkadan o'tish huquqi
chmod o+x "/home/$OWNER" "$PROJECT_DIR"

# --- systemd --------------------------------------------------------------
info "systemd fayllari nusxalanmoqda"
cp test100.socket "$SYSTEMD_DIR/$APP.socket"
cp test100.service "$SYSTEMD_DIR/$APP.service"
systemctl daemon-reload
systemctl enable --now "$APP.socket"
systemctl enable "$APP.service"
systemctl restart "$APP.service"

# --- nginx ----------------------------------------------------------------
info "nginx konfiguratsiyasi nusxalanmoqda"
cp nginix.conf "$NGINX_AVAILABLE"
ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
nginx -t
systemctl reload nginx

# --- Tekshirish -----------------------------------------------------------
sleep 2
if systemctl is-active --quiet "$APP.service"; then
    info "$APP.service ishlayapti"
else
    journalctl -u "$APP.service" -n 30 --no-pager
    fail "$APP.service ishga tushmadi (log yuqorida)"
fi

STATUS=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $DOMAIN" http://127.0.0.1/ || true)
info "http://$DOMAIN/ javobi: $STATUS"

cat <<EOF

Tayyor! Sayt: http://$DOMAIN/
Admin yaratish (birinchi marta):
    cd $PROJECT_DIR && sudo -u $OWNER .venv/bin/python manage.py createsuperuser
Loglar:
    journalctl -u $APP.service -f
EOF
