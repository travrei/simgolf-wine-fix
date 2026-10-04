# SimGolf Wine Fix

[Read in English](README.md)

Correção comunitária de renderização do Sid Meier's SimGolf no Linux com Wine.

**A v0.2.0 remove a exigência de um SHA-256 específico da DLL original.** O instalador verifica estrutura, imports necessários, formato de pixels, chamadas OpenGL e relocações. Arquivos compatíveis com metadados, conteúdo adicional ou checksums diferentes podem receber o patch, preservando os bytes não relacionados à correção.

A correção gráfica injetada permanece igual à v0.1.0. Seu resultado visual foi confirmado em 800×600, com Fedora 44, Wine 11.0 Staging, Radeon RX 6750 XT e Mesa 26.2.3. O lançamento continua preliminar; versões com outra estrutura interna não são automaticamente compatíveis.

## Histórico e uso de IA

Comecei a engenharia reversa do SimGolf em 2024. Conforme as ferramentas de IA evoluíram, continuei o projeto com "vibe coding", usando IA para desenvolver e testar este patch.

— Andrei Esteves dos Reis Bonfante (@travrei)

## Instalar

Requer Linux, Python 3.9+, Wine com OpenGL funcionando e uma instalação existente do jogo. Aplicar o pacote não exige compilador nem bibliotecas Python adicionais.

Feche o jogo. Extraia o pacote e abra um terminal nessa pasta:

```bash
python3 patch.py check '/caminho/para/SimGolf'
python3 patch.py apply '/caminho/para/SimGolf'
```

Também é possível informar o caminho completo de Terrain.dll. O instalador cria `Terrain.dll.simgolf-wine-fix.backup` ao lado da DLL antes de instalar a correção. Um backup existente precisa corresponder exatamente ao arquivo original atual. Aplicar novamente reconhece a instalação sem duplicar o patch.

Abra o jogo a partir da pasta dele:

```bash
cd '/caminho/para/SimGolf'
wine ./golf.exe
```

## Restaurar

Na pasta em que extraiu o patch:

```bash
python3 patch.py restore '/caminho/para/SimGolf'
```

**Guarde o backup.** Para variantes com hashes diferentes, ele também é necessário para reconhecer um arquivo já corrigido. A restauração verifica se reconstruir o patch daquele backup produz exatamente a DLL atual; depois recupera os bytes originais. Modificações posteriores na DLL corrigida são recusadas, evitando sua sobrescrita. O backup permanece após a restauração.

## Compatibilidade

O código injetado v3 usa endereços internos fixos. A v0.2.0 verifica o layout x86 PE32 necessário, endereço-base, limites das seções, funções importadas nos endereços esperados, estrutura do formato de pixels, 10 chamadas/saltos de glFlush, 22 de glBegin e suas relocações. Arquivos truncados, layouts incompatíveis e alterações anteriores conflitantes são recusados.

Não há exigência de um hash fixo para a DLL original do usuário. O payload distribuído mantém sua verificação de integridade. Estes hashes servem como referências de regressão, não como lista de versões permitidas:

- Original de referência: `378e61d2f2061f85e517eade8b64e92ecde00d30ab866c091d55cb737adce0a4`
- Corrigida de referência: `96befb7be17227e33b9a0b1bef84b22777124f9dd80750dffe1a7cde87fd4d6b`

Compatibilidade estrutural não comprova o funcionamento de qualquer binário modificado. Além da DLL de referência, os testes automáticos cobrem cinco variações compatíveis sintéticas. Outras versões ainda exigem testes durante o jogo.

## Escopo

O patch sincroniza o bitmap GDI e o framebuffer OpenGL, incluindo conversão RGB555/RGB565. Altera somente Terrain.dll e mantém a resolução original. Widescreen não está incluído.

Uma instalação da ISO completa pode falhar antes da renderização, por exemplo com erro no driver SecDrv. Este patch não altera golf.exe nem resolve esse problema separado de inicialização. A Terrain.dll original da ISO examinada durante o desenvolvimento já era compatível com a v0.1.0.

Executáveis, DLLs e recursos do jogo não estão incluídos. O pacote contém apenas o código próprio do patch, seu payload compilado, documentação e testes.

## Compilar e testar

Recompilar exige GCC com suporte freestanding a `-m32`, GNU binutils com elf_i386, Bash e Python 3. Cabeçalhos do Windows e MinGW não são necessários.

```bash
bash build_payload.sh
python3 -m unittest discover -s tests
SIMGOLF_ORIGINAL_DLL='/caminho/para/Terrain.dll-original' python3 -m unittest discover -s tests
```

Os testes de integração usam a DLL original de referência acima, criando cópias temporárias. Ela não é distribuída. Sem a variável de ambiente, esses testes são ignorados. A compilação grava em `build/` e preserva o payload distribuído. GCC 16.2.1 reproduziu exatamente esse payload. O instalador não aceita silenciosamente bytes diferentes produzidos por outro compilador. A seção injetada reúne código e estado mutável, portanto o aviso RWX do linker é esperado.

Consulte [VALIDATION.md](VALIDATION.md) para os resultados. Ao relatar problemas, informe versão do patch/Wine, GPU/driver, resolução, saída de `check` e passos para reproduzir.

## Licença

O código original do projeto usa [licença MIT](LICENSE). SimGolf e seus recursos permanecem sob os direitos de seus respectivos titulares. Projeto comunitário não oficial.
