# Termux Manager Android | 0.1.0-alpha.2

Projeto de **integração para APK Android de uso particular**, com o terminal oficial do Termux e uma cópia integrada do [TermuxManager](https://github.com/drilemoz/TermuxManager). O projeto **não contém nem distribui o APK oficial ou todo o código do Termux**. O workflow obtém os dois projetos públicos no momento da compilação.

## Estado da entrega

- **Implementado em código-fonte:** integração pós-bootstrap do Termux, pacote offline do Manager, comandos `manager`/`mm`, autoinicialização opcional, proteção contra *Zip Slip*, instalação sem sobrescrever uma pasta `~/scripts/manager` já existente, verificação do manifesto de origem, correção local dos links antigos do repositório, versionamento de APK e GitHub Actions.
- **Testado localmente:** testes sintéticos do integrador Python; compilação do módulo Java com stubs Android e simulação de instalação, preservação de alterações e bloqueio de extração maliciosa.
- **Ainda não testado:** compilação completa do app Android, APK real, funcionamento em telefone, integração com complementos oficiais, permissões Android e atualização de dados de uma instalação anterior.

## Como compilar pelo GitHub Actions

1. Crie um repositório **privado** novo, por exemplo `Termux-Manager-Android`.
2. Envie o conteúdo **interno desta pasta** à raiz do repositório existente, substituindo os arquivos anteriores e mantendo `.github/workflows` (inclusive arquivos e pastas ocultos).
3. Acesse **Actions → Gerar Termux Manager APK → Run workflow**; a compilação também é acionada em `push` na branch `main` quando os arquivos do projeto mudam.
4. O workflow baixa `termux/termux-app` (`master`) e `drilemoz/TermuxManager` (`main`), verifica os hashes e a sintaxe do Manager, aplica a integração, baixa o bootstrap oficial com conferência SHA-256 feita pelo Gradle do Termux e executa `:app:assembleDebug`.
5. Se a compilação for aprovada, baixe o pacote **Termux-Manager-APK-build-N** em **Actions → workflow → Artifacts**. Ele contém o APK e `origins.txt`.
6. Quando houver erro, será enviado apenas **Termux-Manager-DIAGNOSTICO-build-N**. Esse artifact **não contém APK**. O SDK é preparado com `android-actions/setup-android@v4`, explicitando `packages: platform-tools` para não solicitar o pacote removido `tools`.

O `BUILD_NUMBER` está em `2` (APK `versionCode` calculado como `Termux versionCode * 1000 + BUILD_NUMBER`). Aumente esse número em builds que precisem instalar como atualização da versão anterior; a chave de assinatura também precisa permanecer a mesma.

> Por segurança, o APK Debug criado com a chave pública de teste que já acompanha o repositório oficial **não deve ser distribuído como uma versão confiável de produção**. Para atualizações pessoais estáveis e assinatura realmente privada, configurar uma keystore própria em uma próxima etapa.

## Primeira instalação

A identidade Android permanece **`com.termux`**, mantendo os caminhos Linux nativos do bootstrap. Isso implica:

- APK assinado com uma chave diferente **não instala por cima do Termux oficial**. É preciso primeiro fazer **backup**, garantir uma cópia recuperável e então remover o Termux antigo. A desinstalação pode apagar `$HOME`, `$PREFIX` e o histórico dos projetos.
- Os complementos Termux:API, Termux:Boot, Termux:Widget etc. podem exigir reinstalação/assinatura compatível. Não assuma que funcionarão com o APK privado.
- A primeira inicialização offline instala o Manager em `~/scripts/manager`, cria `manager` e `mm` em `$PREFIX/bin` e acrescenta um bloco marcado a `~/.bash_profile`, sem apagar seu conteúdo anterior.
- O Termux continua sendo um terminal normal: ao sair do menu do Manager, o Bash permanece disponível.
- O **código do Manager** vem dentro do APK. Pacotes Linux adicionais (Node, Python, Fish, Git, PRoot e outros) precisam de internet quando instalados pelo assistente. A permissão de armazenamento ainda é solicitada pelo Android.

### Desativar ou reativar a abertura automática

Após sair do Manager e voltar ao Bash:

```bash
# Desativa abertura automática nas próximas sessões:
touch ~/.termux-manager-no-autostart

# Reativa:
rm -f ~/.termux-manager-no-autostart

# Abre manualmente:
manager
# ou:
mm
```

Também é possível iniciar uma sessão com `TERMUX_MANAGER_DISABLE_AUTOSTART=1` quando apropriado.

## Importante: URL antiga no TermuxManager

O repositório fornecido é `drilemoz/TermuxManager`, mas `install.sh`, `manager.sh` e o atualizador possuem links internos apontando para `adriedsonlemoz/TermuxManager`. Durante a **montagem do bundle**, o integrador substitui a origem antiga pela nova e recalcula os hashes do manifesto da **cópia embutida**. A configuração de shell também fornece as URLs corretas como variáveis de ambiente para as atualizações executadas pelo menu.

**O repositório `drilemoz/TermuxManager` não é alterado automaticamente.** Convém corrigir também as URLs no repositório de origem para que futuras instalações comuns funcionem sem depender do APK integrado.

## Como testar o código desta entrega

```bash
python3 -m unittest discover -s tests -p 'test_integration.py' -v
python3 tests/test_java_bundle.py
python3 -m unittest discover -s tests -p 'test_workflow.py' -v
```

Este ZIP é uma **base de integração / projeto de construção**, não um APK pronto e não comprova que o Gradle ou um aparelho Android tenham sido testados com sucesso. Compilações futuras devem ser verificadas nos logs do Actions e no telefone antes de substituir uma instalação anterior.

## Fontes e licença

- Termux: https://github.com/termux/termux-app
- TermuxManager: https://github.com/drilemoz/TermuxManager

O projeto de integração contém arquivos próprios; os direitos e licenças dos componentes originais devem continuar sendo respeitados. A modificação privada é permitida pela GPLv3 do Termux; redistribuição do APK pode criar obrigações adicionais.

## Correção alpha.2 (workflow #1)

O primeiro workflow (14/10/2026) parou no `android-actions/setup-android@v3`, que tentava instalar o pacote SDK Android obsoleto `tools` e retornou `Failed to find package 'tools'`. O código Android **não chegou a compilar**. A alpha.2 usa `android-actions/setup-android@v4`, com apenas `platform-tools` na configuração inicial e instalação separada de NDK, plataforma e build-tools. O workflow agora executa testes prévios e diferencia um APK realmente produzido de um arquivo exclusivo de diagnóstico.
