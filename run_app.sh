# Запускаем миграции и тесты
docker compose up -d postgres-test
docker compose run --rm migrate-test
docker compose run --rm tests

# Запускаем приложение
docker compose up -d web postgres nginx