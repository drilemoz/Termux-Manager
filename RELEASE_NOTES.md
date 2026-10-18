# Termux Manager 0.1.0-alpha.3

**Código-fonte de integração, sem APK pré-compilado.**

- Tema azul inspirado no Windows PowerShell clássico, aplicado apenas quando não há cores existentes em `~/.termux/colors.properties`.
- Identidade visual com ícone terminal + engrenagem e nome Termux Manager.
- Snapshot offline do TermuxManager 1.0.126 incluído no projeto, validado por SHA-256.
- Instalação para prefixo já existente e reparo conservador de arquivos ausentes.
- SHA-256 por arquivo, rejeição de entradas ZIP estranhas e integração com rollback.
- Assinatura privada via GitHub Secrets sem fallback para assinatura pública de testes.
- Comando `manager-autostart` para controlar ou remover autoinicialização sem apagar configurações do usuário.

**Testes locais:** 13 testes Python, compilação Java simulada com cenários de proteção e reparo, 59 scripts Bash do snapshot verificados, e integração real do snapshot 1.0.126 em estrutura sintética do Termux. **Ainda não realizado:** build Gradle/Android e teste em celular.

A configuração da keystore com `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS` e `KEY_PASSWORD` é obrigatória antes de rodar GitHub Actions.
