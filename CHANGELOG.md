# Histórico

## 0.1.0-alpha.1 (2026-10-14)
- Estrutura inicial para fork pessoal do Termux, sem alterar `com.termux`.
- Integração após a extração do bootstrap oficial com instalação do Manager por asset local.
- Instalação com diretório temporário, bloqueio de Zip Slip, limitações de tamanho e proteção dos dados do usuário.
- Atalhos `manager`/`mm` e inicialização opcional a partir do Bash de login.
- Correção temporária da origem GitHub do Manager na cópia embutida, com manifesto recalculado.
- Workflow GitHub Actions para build Debug e rastreabilidade de commits.
- Testes locais Python e Java com ambiente simulado.
- **Pendente:** Gradle real, validação APK e testes Android.
