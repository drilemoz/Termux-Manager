# Histórico

## 0.1.0-alpha.3 (2026-10-18)
- Tema padrão azul do Windows PowerShell clássico `#012456`, texto `#CCCCCC`, cursor branco em `~/.termux/colors.properties` se ausente; preserva personalizações.
- Ícone original terminal + engrenagem com densidades e versões adaptativas/redondas; nome Termux Manager em recursos de tradução.
- Manager atualizado para snapshot offline 1.0.126 (138 arquivos verificados por SHA-256), armazenado em `vendor/` com arquivo SHA256SUMS; Termux fixado em `8629e632fcb95da272221be327db653fb24befe9`.
- Novo comando `manager-autostart` para habilitar/desabilitar e remover o bloco de autoinicialização sem apagar o restante da `.bash_profile`.
- Instalação garantida mesmo com `$PREFIX` já existente, em worker antes de liberar terminal; instalação idempotente e reparo somente dos arquivos ausentes em instalações identificadas como gerenciadas.
- Verificação SHA-256 individual de todas as entradas ZIP por índice de integridade incluído no APK, rejeitando entradas não declaradas, duplicadas e caminhos perigosos.
- Empacotamento estritamente limitado aos arquivos do `MANIFEST.json`, excluindo arquivos extras não declarados.
- Integração com validação prévia e rollback das alterações em erro de escrita; não altera o Termux quando um requisito de versão/âncora falha.
- Build exige assinatura própria por quatro GitHub Secrets e valida assinatura produzida com `apksigner`; removido fallback intencional da assinatura pública de testes.
- Ampliação de testes locais (simulações de reparo, hash, tema e entradas ZIP extras), sincronização para `BUILD_NUMBER=3` e documentação.
- **Pendente:** compilação Android completa pelo Actions, compatibilidade de atualização do Termux e teste físico dos recursos integrados.

## 0.1.0-alpha.2 (2026-10-14)
- Corrigido setup Android SDK do GitHub Actions: `setup-android@v3` tentava instalar SDK `tools`, removido do catálogo; atualizado para `setup-android@v4`, `packages: platform-tools`.
- Instalação explícita do NDK e SDK 36; testes Python/Java antes do Gradle; Artifacts separados de sucesso e falha.

## 0.1.0-alpha.1 (2026-10-14)
- Estrutura inicial para personalização do Termux sem alterar `com.termux`.
- Integração após bootstrap, comandos `manager`/`mm`, autoinicialização opcional, bundle offline.
- Corrigidos links antigos do repositório do Manager na cópia integrada.
