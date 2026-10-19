# Termux Manager 0.1.0-alpha.5

**Fonte de integração Android, sem APK pré-compilado.**

- TermuxManager 1.0.133 incorporado: 147 arquivos SHA-256 conferidos.
- Central de execução com opção [T] Iniciar tudo, seleção e persistência do projeto preferido, diagnóstico de MariaDB/phpMyAdmin e portas; nenhum serviço é iniciado automaticamente apenas ao abrir o APK.
- Melhorias de importação (navegador de arquivos e resolução simplificada de conflitos), phpMyAdmin local e testes adicionais da upstream.
- Preserva tema azul PowerShell `#012456` inclusive na barra de teclas Android, ícone próprio, Fish opcional no assistente, painel de `pkg/apt` com atividade real.
- Upgrade de instalações gerenciadas preserva arquivos editados pelo usuário; instalações externas não são sobrescritas.
- Termux base `0.118.0`, APK esperado `0.118.0+tm.5`, versionCode `118005`, package ID `com.termux`, assinatura privada obrigatória via quatro Secrets existentes.
- Build Gradle Android e teste no celular ainda pendentes. Antes de instalar, faça backup dos dados e confira assinatura compatível.
