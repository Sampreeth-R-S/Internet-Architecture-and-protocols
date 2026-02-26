# PowerShell script to run docker-compose with N server instances
# Usage: .\run_servers.ps1 -NumServers 5

param(
    [Parameter(Mandatory=$true)]
    [ValidateRange(1, [int]::MaxValue)]
    [int]$NumServers
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Chat Server Multi-Instance Launcher" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Generating configuration for $NumServers server instance(s)..." -ForegroundColor Yellow

# Run the Python script
python generate_docker_compose.py $NumServers

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Starting services with Docker Compose..." -ForegroundColor Yellow
    Write-Host ""
    docker-compose up --build
} else {
    Write-Host "Error: Failed to generate docker-compose.yml" -ForegroundColor Red
    exit 1
}
