"""Small, reviewed changes on the pinned upstream Manager snapshot.
These are made AFTER verifying its official hashes; the original ZIP stays intact.
"""
import hashlib
import json
from pathlib import Path


def replace_once(s, old, new, label):
    n=s.count(old)
    if n != 1:
        raise RuntimeError(f"Manager overlay anchor missing/ambiguous ({label}: {n})")
    return s.replace(old,new)


def apply_manager_overlays(folder: Path):
    setup=folder/'modules/termux_setup.sh'
    s=setup.read_text(encoding='utf-8')
    s=replace_once(s,'for etapa in storage update tools shortcut; do',
       'for etapa in storage update tools shortcut fish; do','wizard progress items')
    s=replace_once(s,'            shortcut) linhas+=("$status Atalho global") ;;',
       '            shortcut) linhas+=("$status Atalho global") ;;\n'
       '            fish) linhas+=("$status Fish como shell padrão") ;;', 'wizard progress names')
    s=replace_once(s,'        "4. Configurar o atalho global"',
       '        "4. Configurar o atalho global" \\\n        "5. Fish como shell padrão (opcional)"', 'wizard steps')
    anchor='    # Só conclui definitivamente quando o armazenamento também estiver\n'
    inject='''    # Fish é instalado nas ferramentas recomendadas, mas habilitar como shell
    # padrão altera o comportamento do terminal. Perguntar uma única vez.
    # Não mexe no shell de quem já concluiu o assistente em versões anteriores.
    if ! first_run_stage_done fish && ! grep -Fxq 'fish=skipped' "${FIRST_RUN_STATE_FILE:-/dev/null}" 2>/dev/null; then
        if command -v fish >/dev/null 2>&1 && \\
            confirmar_acao "Ativar Fish automaticamente nas novas sessões?" "s"; then
            FISH_CONFIG_COMPLETA=true
            if configurar_sugestoes_fish && definir_fish_padrao; then
                first_run_mark_stage fish
                caixa_simples "🐟 Fish ativado" \\
                    "Novas sessões abrirão Fish automaticamente." \\
                    "Bash manual: MANAGER_KEEP_BASH=1 bash"
            else
                warn "Não foi possível ativar Fish automaticamente. Ajuste depois em Configurações."
                printf 'fish=skipped\\n' >> "$FIRST_RUN_STATE_FILE"
            fi
            FISH_CONFIG_COMPLETA=false
        else
            printf 'fish=skipped\\n' >> "$FIRST_RUN_STATE_FILE"
            info "Fish automático não ativado. Pode ser configurado depois no menu."
        fi
    fi

'''
    s=replace_once(s,anchor,inject+anchor,'wizard fish activation')
    setup.write_text(s,encoding='utf-8')

    ui=folder/'modules/termux_packages_ui.sh'
    s=ui.read_text(encoding='utf-8')
    s=replace_once(s,'    linha_conteudo "$n" "$(barra_percentual_simples "$pct" "$interno")" "$C_CYAN"; n=$((n+1))',
        '''    # pkg/apt não expõem porcentagem confiável em todas as fases.
    # Para processo ativo, mostrar indicador indeterminado, nunca percentual fictício.
    if [ "$pct" = "-1" ]; then
        linha_conteudo "$n" "⏳ Instalação em andamento • progresso variável" "$C_CYAN"
    else
        linha_conteudo "$n" "$(barra_percentual_simples "$pct" "$interno")" "$C_CYAN"
    fi
    n=$((n+1))''', 'live package progress')
    ui.write_text(s,encoding='utf-8')

    monitor=folder/'modules/termux_packages_monitor.sh'
    s=monitor.read_text(encoding='utf-8')
    s=replace_once(s,'        assinatura="$pct|$linhas|$decorrido|$ocioso"',
                   '        assinatura="indeterminado|$linhas|$decorrido|$ocioso"', 'pkg signature')
    s=replace_once(s,'PKG_PREVIEW_LINES="$linhas" tela_operacao_termux "$titulo" "$pct" "$atividade" "$detalhe"',
                   'PKG_PREVIEW_LINES="$linhas" tela_operacao_termux "$titulo" -1 "$atividade" "$detalhe"', 'pkg activity')
    # A barra simulada de 1% por dois segundos não é progresso real.
    s=replace_once(s,'        if [ "$pct" -lt "$limite" ] && [ $((iter % 2)) -eq 0 ]; then pct=$((pct + 1)); fi\n',
                   '', 'simulated percent increment')
    monitor.write_text(s,encoding='utf-8')

    manifest=folder/'MANIFEST.json'
    m=json.loads(manifest.read_text(encoding='utf-8'))
    for p in [setup,ui,monitor]:
        name=p.relative_to(folder).as_posix()
        assert name in m['files'],name
        m['files'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return 'Fish opt-in wizard; real-status package console'
