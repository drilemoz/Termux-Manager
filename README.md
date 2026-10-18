# Termux Manager | 0.1.0-alpha.3

Projeto Android para gerar, pelo GitHub Actions, um APK privado do **Termux** com **TermuxManager 1.0.126** incorporado, nome de aplicativo **Termux Manager**, ícone azul de terminal + engrenagem e aparência padrão **PowerShell clássico**.

## Identidade e versão

- **Nome visível no Android:** Termux Manager, inclusive traduções locais que declararem `application_name`.
- **Package ID:** `com.termux` (mantido obrigatoriamente para compatibilidade com o bootstrap e caminhos Linux).
- **Versão da integração:** `0.1.0-alpha.3` / `BUILD_NUMBER=3`.
- **TermuxManager incorporado:** snapshot `vendor/TermuxManager-v1.0.126.zip` verificado por SHA-256 `c7b1b132a561e68fff8a90221769b30ef45e36d4bdfeb5d3b9750af68e8235e0`, obtido da pasta do projeto no Google Drive; MANIFEST declara 1.0.126 e teve os 138 hashes confirmados em 18/10/2026.
- **Termux base:** `termux/termux-app` no commit `8629e632fcb95da272221be327db653fb24befe9`, com `versionName` upstream `0.118.0` e `versionCode` upstream `118`, verificados no código.
- **APK versionName:** `0.118.0+tm.3`; **versionCode:** `118003` (calculado na integração). Atualização in-place exige também mesma assinatura e package ID.

O código-fonte completo do **Termux Android** não está neste ZIP: o GitHub Actions baixa esse repositório no commit fixo. O TermuxManager 1.0.126 **já está dentro do ZIP**, no diretório `vendor/`, e é validado por SHA-256 no workflow e pelos hashes individuais do `MANIFEST.json`. Novas releases do Manager não entram automaticamente; é necessário revisar e substituir o snapshot verificado.

## Visual padrão

- Fundo do terminal: azul `#012456` (PowerShell clássico).
- Texto: `#CCCCCC`; cursor branco `#FFFFFF`.
- Tema aplicado ao arquivo `~/.termux/colors.properties`, **somente quando ele ainda não existe**, durante a inicialização do Termux depois do bootstrap, sem alterar a configuração de quem já personalizou o terminal.
- Ícone: arte original com prompt `>_` e engrenagem (`integration/branding/source-icon.png` como fonte), empacotada nos `mipmap-*` (`mdpi`, `hdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`), ícones redondos e adaptativos.
- Para voltar ao visual de origem, altere ou exclua `~/.termux/colors.properties` e abra nova sessão/recarregue o terminal. Em uma instalação existente com tema personalizado, **o tema azul não sobrescreve as cores já definidas**.

## Instalação do Manager embutido

- Primeira instalação: após concluir o bootstrap, verifica o bundle e instala em `~/scripts/manager`; cria atalhos `manager` e `mm` em `$PREFIX/bin` e acrescenta um bloco de autoinicialização a `~/.bash_profile`.
- Prefixo já existente: executa a verificação em uma thread antes de liberar a sessão do terminal, resolvendo o caso em que o bootstrap não era repetido.
- Reparo: apenas em pastas **gerenciadas por essa integração**, identificadas por `.termux-manager-bundle-installed`, os arquivos faltantes são restaurados, sem substituir os existentes. Instalações preexistentes ou modificadas sem marcador são preservadas.
- Proteções: caminhos canônicos, rejeição de entradas ZIP desconhecidas/duplicadas, limite de tamanho e entradas, hash SHA-256 de **cada arquivo** confrontado com índice separado integrado ao APK, origem validada pelo MANIFEST.json e pacote contendo somente arquivos declarados.
- Atualizações do APK **não sobrescrevem a instalação já existente do Manager**; o bundle 1.0.126 será instalado automaticamente apenas quando ainda não houver uma pasta Manager anterior. Para atualizar uma instalação existente do Manager, use o procedimento de atualização do próprio Manager após backup.
- Um erro no componente opcional do Manager não apaga o `$PREFIX` do Termux.

Desativar autoinicialização do menu (`manager` e `mm` continuam disponíveis):

```bash
touch ~/.termux-manager-no-autostart
```

Reativar:

```bash
rm -f ~/.termux-manager-no-autostart
```

O atalho `manager-autostart` oferece também `manager-autostart status`, `manager-autostart disable`, `manager-autostart enable` e `manager-autostart remove`, que remove apenas o bloco delimitado da `.bash_profile` preservando o restante. Use `remove` se não quiser mais nenhuma alteração de inicialização automática; a versão atual não fornece um comando para recriar esse bloco sem nova execução do instalador.

## Compilar no GitHub Actions

1. Crie ou atualize um repositório GitHub de preferência **privado**, mantendo os arquivos e a pasta `.github/workflows` na raiz.
2. **Antes de executar o workflow, configure a assinatura privada**. São obrigatórios os Secrets `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS` e `KEY_PASSWORD`. O arquivo do keystore deve conter a chave privada e ser representado em Base64 numa única linha (JKS ou PKCS12). Não envie keystore ou Secrets ao repositório nem inclua nos ZIPs públicos.
3. Execute **Actions → Gerar Termux Manager APK → Run workflow** ou publique uma alteração na branch `main`.
4. O workflow fixa o commit do Termux e confere o snapshot do Manager, prepara Android SDK 36/NDK 29, valida Python/Java/Bash, integra, compila `:app:assembleDebug`, verifica a assinatura usando `apksigner` e disponibiliza **Termux-Manager-APK-build-N** nos Artifacts em caso de sucesso.
5. Caso falhe, consulte o log e o Artifact **Termux-Manager-DIAGNOSTICO-build-N**. Falta de Secrets faz o build **falhar intencionalmente**; nunca há fallback silencioso para `testkey_untrusted.jks`.

Uma chave própria pode ser criada num ambiente protegido usando `keytool` (Java JDK), por exemplo:

```bash
keytool -genkeypair -keystore TermuxManager-privada.p12 -storetype PKCS12 \
  -alias termux-manager -keyalg RSA -keysize 3072 -validity 10000
base64 -w 0 TermuxManager-privada.p12 > keystore-base64.txt
```

Informe as senhas e alias reais apenas no GitHub Secrets. No **GitHub Manager** use **Repositório → Secrets → Importar** para importar um arquivo `.env` UTF-8 com os quatro valores, caso prefira, mas não guarde esse arquivo no GitHub. Salve um backup confiável da keystore: se perdê-la, os próximos APKs não atualizarão os anteriores. O workflow usa a tarefa `assembleDebug` com **chave privada personalizada**, não uma assinatura Debug pública.

## Segurança na instalação

**Importante: o aplicativo continua com o package ID `com.termux`.** APKs de assinatura diferente não substituem o Termux instalado. Antes de qualquer desinstalação, faça backup externo verificável de `$HOME`, `$PREFIX` e dos arquivos de projetos. Complementos Termux:API, Termux:Boot, Termux:Widget etc. podem exigir assinaturas compatíveis e devem ser testados antes de uso.

Pacotes Linux extras instalados pelo Manager ainda podem exigir internet; incorporar os scripts não incorpora todos os pacotes de distribuição.

## Testes e limitações

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/test_java_bundle.py
```

Esses testes verificam integração transacional, hashes, preservação de dados, proteção contra entradas maliciosas, reparo e cores usando fixtures e Android stubs. **Não representam um build Gradle/Android real nem testes num telefone físico.** O APK somente será validado após GitHub Actions completar a compilação e depois de testes em aparelho.

## Fontes e licenças

- Termux: https://github.com/termux/termux-app (GPLv3)
- TermuxManager: https://github.com/drilemoz/TermuxManager

O ícone desta integração é arte original. Para redistribuição do APK, observe as obrigações de licença do Termux e de outras dependências.
