# ============================================
# Exportar projeto para .txt com divisão por limite de caracteres
# Uso: .\exportar_projeto.ps1 [-Root <caminho>] [-Output <nome_base>] [-MaxChars <limite>]
# Exemplo: .\exportar_projeto.ps1 -Root "C:\Users\CassioJ\Documents\frota_web" -Output "dump" -MaxChars 50000
# ============================================

param(
    [string]$Root = ".",
    [string]$Output = "projeto_dump",
    [int]$MaxChars = 50000   # limite de caracteres por arquivo .txt
)

# Extensões permitidas
$includeExt = @('.py','.html','.js','.css','.json','.md','.txt','.sql','.ini','.cfg','.yml','.yaml','.toml','.sh')

# Pastas ignoradas
$excludeDirs = @('venv','.git','__pycache__','instance','node_modules','.idea','.vscode','migrations','dist','build','logs')

# Caminho raiz absoluto
$rootPath = (Resolve-Path -Path $Root).Path

# Coleta arquivos filtrados
$arquivos = Get-ChildItem -Path $rootPath -Recurse -File | Where-Object {
    $ext = $_.Extension.ToLower()
    $full = $_.FullName
    $skip = $false
    foreach ($dir in $excludeDirs) {
        if ($full -like "*\$dir\*") { $skip = $true; break }
    }
    (-not $skip) -and ($includeExt -contains $ext)
}

# Inicializa buffer e contador de partes
$buffer = New-Object System.Text.StringBuilder
$parteAtual = 1
$arquivosNaParte = 0
$totalArquivos = $arquivos.Count

foreach ($arquivo in $arquivos) {
    $rel = $arquivo.FullName.Substring($rootPath.Length + 1)
    $cabecalho = "`n===== $rel =====`n"
    $conteudo = ""

    try {
        $raw = Get-Content -Path $arquivo.FullName -Raw -Encoding UTF8 -ErrorAction Stop
        # trunca individualmente se ultrapassar 150k para evitar arquivos muito grandes
        if ($raw.Length -gt 150000) {
            $raw = $raw.Substring(0, 150000) + "`n`n... [ARQUIVO TRUNCADO]"
        }
        $conteudo = $raw
    } catch {
        $conteudo = "<ERRO AO LER ARQUIVO: $($_.Exception.Message)>"
    }

    $bloco = $cabecalho + $conteudo + "`n"
    $tamanhoBloco = $bloco.Length

    # Se adicionar o bloco estourar o limite, salva a parte atual e inicia nova
    if (($buffer.Length + $tamanhoBloco) -gt $MaxChars -and $buffer.Length -gt 0) {
        # Salva parte atual
        $nomeParte = "${Output}_parte${parteAtual}.txt"
        $buffer.ToString() | Out-File -FilePath $nomeParte -Encoding utf8
        Write-Host "✅ Parte $parteAtual salva: $nomeParte (arquivos: $arquivosNaParte)" -ForegroundColor Green

        # Reinicia buffer
        $buffer.Clear() | Out-Null
        $parteAtual++
        $arquivosNaParte = 0

        # Adiciona indicador de continuação no início da nova parte
        [void]$buffer.AppendLine("<< Continuação da parte anterior >>`n")
    }

    [void]$buffer.Append($bloco)
    $arquivosNaParte++
}

# Salva a última parte (se houver conteúdo restante)
if ($buffer.Length -gt 0) {
    $nomeParte = "${Output}_parte${parteAtual}.txt"
    $buffer.ToString() | Out-File -FilePath $nomeParte -Encoding utf8
    Write-Host "✅ Parte $parteAtual salva: $nomeParte (arquivos: $arquivosNaParte)" -ForegroundColor Green
}

Write-Host "`n📄 Exportação concluída." -ForegroundColor Cyan
Write-Host "📁 Total de arquivos processados: $totalArquivos" -ForegroundColor Cyan
Write-Host "📑 Partes geradas: $parteAtual" -ForegroundColor Cyan