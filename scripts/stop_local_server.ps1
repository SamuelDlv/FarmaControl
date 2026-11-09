param([Parameter(Mandatory = $true)][string]$AppPath)
$ErrorActionPreference = 'Stop'
$stop = $null
$done = $null
try {
    $canonicalPath = (Resolve-Path -LiteralPath $AppPath).ProviderPath.ToLowerInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonicalPath))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
    $name = 'Local\FarmaControl-' + $digest
    try {
        $stop = [Threading.EventWaitHandle]::OpenExisting($name + '.Stop')
    } catch [Threading.WaitHandleCannotBeOpenedException] {
        Write-Host 'Nenhum servidor FarmaControl desta pasta com encerramento cooperativo.'
        Write-Host 'Se iniciou uma versao anterior, use Ctrl+C na janela do servidor e reinicie.'
        exit 0
    }
    $done = [Threading.EventWaitHandle]::OpenExisting($name + '.Done')
    [void]$stop.Set()
    Write-Host 'Aguardando o FarmaControl concluir as requisicoes em andamento...'
    if (-not $done.WaitOne(30000)) {
        throw 'O encerramento ainda esta em andamento. Confira a janela do servidor. Nenhum processo foi finalizado a forca.'
    }
    Write-Host 'FarmaControl encerrado. O servico MySQL/MariaDB permanece sob seu controle.'
} catch {
    Write-Host ('Nao foi possivel confirmar o encerramento: ' + $_.Exception.Message)
    exit 1
} finally {
    if ($done) { $done.Dispose() }
    if ($stop) { $stop.Dispose() }
}
