param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

if ($Port -lt 1 -or $Port -gt 65535) {
    throw 'Port must be between 1 and 65535.'
}

waitress-serve --listen="127.0.0.1:$Port" config.wsgi:application
