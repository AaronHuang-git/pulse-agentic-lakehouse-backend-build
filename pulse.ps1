# pulse.ps1 - thin wrapper around `docker compose` for the Pulse stack.
#
# Adds Docker Desktop's bin to PATH for the current call (in case PowerShell
# was opened before Docker Desktop installed) and pins the project's compose
# file + .env so every command "just works" from the repo root.
#
# Usage:
#   .\pulse.ps1 up -d                          # start the stack
#   .\pulse.ps1 up -d --build ingest           # rebuild + start one service
#   .\pulse.ps1 down                           # stop (preserves volumes)
#   .\pulse.ps1 down -v                        # stop + wipe volumes
#   .\pulse.ps1 ps                             # list containers
#   .\pulse.ps1 logs -f ingest                 # tail one service's logs
#   .\pulse.ps1 exec ingest bash               # shell into a container
#   .\pulse.ps1 exec postgres psql -U pulse -d pulse
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

$dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
if (Test-Path $dockerBin) {
    $env:Path = "$dockerBin;$env:Path"
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeFile = Join-Path $root "infra\docker-compose.yml"
$envFile = Join-Path $root ".env"

& docker compose -f $composeFile --env-file $envFile @Args
exit $LASTEXITCODE
