# 1. Saltamos a la raíz del proyecto sin importar desde dónde se llame
Set-Location "S:\dev\microtaller"

Write-Host "Iniciando MicroTaller API..." -ForegroundColor Cyan

# 2. Referencia absoluta al archivo de Docker
docker-compose -f "S:\dev\microtaller\docker\docker-compose.yml" up -d

# 3. Referencia absoluta al entorno virtual y ejecución de Uvicorn
# Usamos el operador '&' para ejecutar el script de activación
& "S:\dev\microtaller\backend\.venv\Scripts\Activate.ps1"

Write-Host "¡Todo listo! Swagger disponible en http://localhost:8000/docs" -ForegroundColor Green

# 4. Iniciamos el servidor (esto mantiene la terminal ocupada con los logs)
cd backend
uvicorn app.main:app --reload