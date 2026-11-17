$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose exec web python manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
docker compose exec web python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Migration drift detected.' }
docker compose exec web python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
docker compose exec web python manage.py spectacular --validate --file /tmp/openapi.yaml
if ($LASTEXITCODE -ne 0) { throw 'API schema validation failed.' }
