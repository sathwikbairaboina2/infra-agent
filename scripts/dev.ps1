# Runs a command in the infra-agent dev container (python, uv, git, terraform, opa).
Set-Location (Resolve-Path "$PSScriptRoot\..")
docker compose run --rm -T dev @args
exit $LASTEXITCODE
