#!/bin/bash
# scripts/setup_alerts.sh - Interactive script to configure email alerts on the VPS
# Run this script on the remote VPS as root.

set -e

echo "🔔 Настройка автоматических оповещений Netdata на email"
echo "--------------------------------------------------------"

# 1. Запрос почты
read -p "Введите вашу почту Gmail (куда слать алерты и через что отправлять): " GMAIL_ADDRESS
if [ -z "$GMAIL_ADDRESS" ]; then
    echo "❌ Почта не может быть пустой."
    exit 1
fi

# 2. Запрос пароля приложения
echo "Для отправки через Gmail вам нужен 'Пароль приложения' (App Password)."
echo "Его можно создать в настройках аккаунта Google (Безопасность -> Двухэтапная аутентификация -> Пароли приложений)."
read -s -p "Введите ваш 16-значный пароль приложения (пароль скрыт при вводе): " GMAIL_PASSWORD
echo "" # Новая строка после скрытого ввода

if [ -z "$GMAIL_PASSWORD" ]; then
    echo "❌ Пароль не может быть пустым."
    exit 1
fi

# Удаляем пробелы, если пользователь скопировал пароль с пробелами (Google показывает его как 'xxxx xxxx xxxx xxxx')
GMAIL_PASSWORD=$(echo "$GMAIL_PASSWORD" | tr -d ' ')

echo "✍️  Запись конфигурации почты в /etc/msmtprc..."
cat << EOF > /etc/msmtprc
# msmtprc - System-wide SMTP configuration for msmtp
defaults
auth             on
tls              on
tls_trust_file   /etc/ssl/certs/ca-certificates.crt
logfile          /var/log/msmtp.log

account          gmail
host             smtp.gmail.com
port             587
from             $GMAIL_ADDRESS
user             $GMAIL_ADDRESS
password         $GMAIL_PASSWORD

account default : gmail
EOF

chmod 600 /etc/msmtprc
chown root:root /etc/msmtprc
touch /var/log/msmtp.log
chmod 666 /var/log/msmtp.log

echo "✍️  Запись конфигурации алертов в /etc/netdata/health_alarm_notify.conf..."
cat << EOF > /etc/netdata/health_alarm_notify.conf
# health_alarm_notify.conf
SEND_EMAIL="YES"
SEND_TELEGRAM="NO"

EMAIL_SENDER="alerts@${GMAIL_ADDRESS}"
DEFAULT_RECIPIENT_EMAIL="${GMAIL_ADDRESS}"
EOF

chmod 644 /etc/netdata/health_alarm_notify.conf
chown root:netdata /etc/netdata/health_alarm_notify.conf

echo "🔄 Перезапуск службы алертов Netdata..."
systemctl restart netdata

echo "🧪 Отправка тестового email..."
echo "Subject: Тест отправки почты с сервера Hetzner

Это тестовое письмо с вашего сервера Hetzner. Если вы его получили, значит авто-оповещения настроены успешно и будут приходить даже при выключенном ноутбуке!" | msmtp -a default "$GMAIL_ADDRESS"

echo "✅ Настройка успешно завершена! Проверьте вашу почту $GMAIL_ADDRESS."
