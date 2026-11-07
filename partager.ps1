# ---------------------------------------------------------------------------
# DealTrack.be — partager le site avec un lien public temporaire
#
#   Clic droit > « Exécuter avec PowerShell », ou dans un terminal :
#       powershell -ExecutionPolicy Bypass -File .\partager.ps1
#
# 1. démarre le site en mode partage (DEBUG désactivé, back-office fermé
#    aux visiteurs d'Internet) sur http://localhost:8000 ;
# 2. ouvre un tunnel Cloudflare et affiche un lien https://….trycloudflare.com
#    à envoyer sur WhatsApp.
#
# Le lien fonctionne tant que cette fenêtre reste ouverte et que le PC est
# allumé. Il change à chaque lancement. Ctrl+C pour tout arrêter.
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$manage = Join-Path $root "backend\manage.py"
$cloudflared = Join-Path $root ".tools\cloudflared.exe"

if (-not (Test-Path $python)) { throw "Environnement virtuel introuvable : $python" }
if (-not (Test-Path $cloudflared)) {
    throw "cloudflared introuvable : téléchargez-le depuis github.com/cloudflare/cloudflared/releases dans $cloudflared"
}

Write-Host "Démarrage du site en mode partage..." -ForegroundColor Cyan
$server = Start-Process -FilePath $python -PassThru -WindowStyle Minimized -ArgumentList @(
    "`"$manage`"", "runserver", "8000", "--insecure", "--noreload",
    "--settings=config.settings.share"
)

try {
    Start-Sleep -Seconds 4
    Write-Host ""
    Write-Host "Ouverture du tunnel. Le lien à partager s'affiche ci-dessous" -ForegroundColor Cyan
    Write-Host "(ligne « https://....trycloudflare.com »)." -ForegroundColor Cyan
    Write-Host ""
    & $cloudflared tunnel --no-autoupdate --url http://localhost:8000
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Write-Host "Site et tunnel arrêtés." -ForegroundColor Yellow
}
