Write-Host "Iniciando MicroTaller API..." -ForegroundColor Cyan
docker-compose -f ./docker/docker-compose.yml up -d
.\backend\.venv\Scripts\activate
Write-Host "¡Todo listo! Swagger disponible en http://localhost:8000/docs" -ForegroundColor Green
