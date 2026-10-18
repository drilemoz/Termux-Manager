# Termux Manager 0.1.0-alpha.4

**Fonte de integração Android, sem APK pré-compilado.**

- TermuxManager 1.0.128 incorporado, manifesto de 142 arquivos e hashes verificados.
- Barra de teclas extras azul PowerShell `#012456` igual ao terminal; não afeta o teclado virtual Android.
- Instalação existente do Manager criada pelo APK anterior migra arquivos originais para 1.0.128 sem substituir mudanças do usuário. Instalações externas não são modificadas.
- Assistente inicial oferece Fish como padrão, com confirmação explícita; adiciona sugestões e autostart ao aceitar. Instalações que já concluíram o assistente ficam intactas.
- Processo `pkg/apt` mostra painel de progresso terminal, sem porcentagem fictícia e com logs recentes; prompts interativos continuam no TTY real. Não há janela Android nativa.
- Manteve ícone original, package `com.termux`, versionCode 118004, assinatura privada por quatro Secrets e proteção contra ZIP malicioso.

Teste de APK Gradle e execução no Android ainda pendentes. Faça backup antes de atualizar/desinstalar o Termux, especialmente se trocar assinatura.
