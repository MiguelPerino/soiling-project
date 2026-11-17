# 10 · Roteiro da apresentação

## Véspera
- [ ] Ensaio completo **na rede que será usada**. `curl http://IP-DO-ESP32/` funciona do computador?
- [ ] IP do ESP32 reservado no roteador; `ESP32_URL` correto; indicador do topo mostra "ESP32 online".
- [ ] Placa gravada com o modelo atual: `model_version` = `soilnet-2x-112-20261116` no resultado (e no `curl http://IP-DO-ESP32/`).
- [ ] Modelo grande baixado (`scripts/download-model.sh --check`); a barra lateral mostra "Modelo grande ativo · resnet50-224-20261116".
- [ ] Bomba testada com água em recipiente; cooldown ajustado; **intervalo e duração** conhecidos pela equipe.
- [ ] Uma foto de painel sujo e uma limpa **salvas no celular e no computador** (reserva).
- [ ] Gemini testado (ou aceitar o plano B).
- [ ] Chave de administrador anotada; navegador do celular com a aba já aberta.
- [ ] Plano B pronto: `docker compose --profile sim ...` (simulador) se o ESP32 falhar.

## Roteiro (≈5 min)
1. ESP32 ligado e online; abrir o sistema no celular. Mostrar o indicador **ESP32 online**.
2. **Analisar**, modo **ESP32**, "Permitir acionar a bomba": tirar foto do painel sujo → mostrar o indicador de processamento.
3. Resultado: "Precisa limpar", confiança, probabilidades. Mostrar a **bomba (LED) acionando** e o texto "Bomba acionada por X s".
4. Repetir com painel limpo: "Não precisa limpar" e "Bomba não acionada" (só "Precisa limpar" aciona).
5. Enviar a foto suja de novo logo depois: mostrar o **intervalo mínimo** (segurança).
6. Mesma foto no modo **Servidor** (ResNet50): resultado mais robusto, marca do limiar na barra e "sem bomba" (o servidor só informa).
7. Aba **Histórico**: o registro, abrir detalhe, corrigir um rótulo (revisão humana).
8. Aba **Painel**: totais por classe e por mecanismo, gráfico.
9. Aba **Assistente**: "quais precisam limpar hoje?" (mostra se foi Gemini ou regras).

## Se algo falhar
| Sintoma | Ação |
| --- | --- |
| Indicador "ESP32 offline" | ver IP/Wi‑Fi/isolamento de clientes; reiniciar o ESP32; mudar para o simulador |
| Câmera não abre | escolher arquivo da galeria; ou "Reanalisar" uma foto do histórico |
| Erro 504 | ESP32 não respondeu: confira energia e Wi‑Fi |
| Erro 502 | firmware/protocolo incompatível: veja o Monitor Serial |
| Bomba não aciona | normal se o resultado for "Não precisa limpar", confiança < 0,50, intervalo mínimo, modo Servidor, ou sem chave de admin (o front avisa) |
| Modo Servidor indisponível | `scripts/download-model.sh` (o motivo aparece na barra lateral); o modo ESP32 segue funcionando |
| Gemini fora | o resumo sai por regras sozinho (`fonte: regras`); seguir |
