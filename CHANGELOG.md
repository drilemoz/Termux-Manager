# Histórico

## 0.1.0-alpha.2 (2026-10-14)
- Corrigido setup Android SDK do GitHub Actions: `setup-android@v3` tentava instalar SDK `tools`, removido do catálogo; atualizado para `setup-android@v4`, `packages: platform-tools`.
- Verificação antecipada de `sdkmanager`, instalação explícita de NDK 29.0.14206865 e SDK 36.
- Rodada de testes de integração e compilação Java simulada ativada no workflow antes do Gradle.
- Artifact `APK` é publicado **somente após build bem-sucedido** e exige presença de `.apk`; falhas produzem Artifact `DIAGNOSTICO` separado.
- `BUILD_NUMBER` incrementado para 2; documentação e status sincronizados.
- Ainda pendentes: build Android completo e teste em aparelho.


## 0.1.0-alpha.1 (2026-10-14)
- Estrutura inicial para fork pessoal do Termux, sem alterar `com.termux`.
- Integração após a extração do bootstrap oficial com instalação do Manager por asset local.
- Instalação com diretório temporário, bloqueio de Zip Slip, limitações de tamanho e proteção dos dados do usuário.
- Atalhos `manager`/`mm` e inicialização opcional a partir do Bash de login.
- Correção temporária da origem GitHub do Manager na cópia embutida, com manifesto recalculado.
- Workflow GitHub Actions para build Debug e rastreabilidade de commits.
- Testes locais Python e Java com ambiente simulado.
- **Pendente:** Gradle real, validação APK e testes Android.
