#!/bin/sh
set -eu

# Loop simples de espera até 02:00, sem depender de cron/supervisord dentro do container —
# um script legível é mais fácil de auditar (projeto de segurança) do que um scheduler
# "caixa-preta". Roda no mesmo container/imagem da aplicação, mas com volumes de db/media
# montados como read-only (ver docker-compose.yml) — este processo só precisa LER o banco
# pra tirar o snapshot, nunca escrever nele.

echo "[backup-scheduler] iniciado, aguardando 02:00 todo dia..."

last_run_date=""
while true; do
    now_date="$(date +%Y-%m-%d)"
    now_time="$(date +%H:%M)"
    if [ "$now_time" = "02:00" ] && [ "$last_run_date" != "$now_date" ]; then
        echo "[backup-scheduler] $(date -Iseconds) disparando backup agendado..."
        python manage.py run_backup || echo "[backup-scheduler] backup falhou, ver logs acima"
        last_run_date="$now_date"
    fi
    sleep 30
done
