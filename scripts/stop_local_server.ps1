# Guia de manutencao: protocolo de parada compartilhado com core/local_server.py.
# O caminho canonico em minusculas e o hash precisam ser identicos nos dois lados.
# Stop pede o encerramento; Done confirma que os handlers e o teardown terminaram.
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
    # Somente sinaliza o evento da instalacao resolvida; nao seleciona processos por nome.
    [void]$stop.Set()
    Write-Host 'Aguardando o FarmaControl concluir as requisicoes em andamento...'
    # O timeout informa que a confirmacao nao chegou; nao implica terminar o processo a forca.
    if (-not $done.WaitOne(30000)) {
        throw 'O encerramento ainda esta em andamento. Confira a janela do servidor. Nenhum processo foi finalizado a forca.'
    }
    Write-Host 'FarmaControl encerrado. O servico MySQL/MariaDB permanece sob seu controle.'
} catch {
    Write-Host ('Nao foi possivel confirmar o encerramento: ' + $_.Exception.Message)
    exit 1
} finally {
    # Handles nativos precisam ser liberados mesmo em timeout ou excecao.
    if ($done) { $done.Dispose() }
    if ($stop) { $stop.Dispose() }
}
