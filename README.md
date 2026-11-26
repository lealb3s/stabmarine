# AP1.5 — Estabilidade transversal em operações de carga

Simulador acadêmico de Beatriz Fabiane Leal Santos. Cada nova sessão começa com um projeto vazio. Você fornece a geometria, a densidade da água, os pesos e os tanques. As curvas KN são calculadas a partir do casco informado, e as curvas GZ são calculadas para as condições que você cadastrar.

## Abrir no computador

Use Python 3.12. Extraia o ZIP, abra um terminal na pasta onde está `app.py` e execute:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Streamlit Community Cloud

Para atualizar o app existente, extraia o ZIP e envie o conteúdo à mesma pasta de `app.py` no repositório e na branch usados pelo Streamlit. Confirme a alteração com **Commit changes**. Inclua todos os módulos Python, `requirements.txt` e a pasta `.streamlit`. O arquivo principal é `app.py`. Para uma nova publicação, use Python 3.12.

## Começar um estudo do zero

1. Em **Casco e curvas KN**, escolha **Importar arquivo** ou **Digitar cotas**. Para digitar, use uma linha por ponto com X, Z e meia-boca em metros. Separe as três medidas por ponto e vírgula ou cole três colunas do Excel. Informe uma largura para cada combinação de baliza e altura.
2. Confira a geometria e a cota de fechamento na prévia e clique em **Aplicar novo casco**. Informe a densidade da água em t/m³ na barra lateral para consultar KN em função do deslocamento.
3. Abra **Cargas e tanques**. Cadastre a embarcação leve com sua massa e as coordenadas do centro de gravidade (X = LCG, Y = TCG e Z = KG). Acrescente as cargas e os tanques da condição inicial e clique em **Aplicar e recalcular**. Para importar o carregamento de uma vez, baixe o modelo vazio em **Importar pesos e tanques do Excel**, preencha as duas abas e clique em **Importar e recalcular**.
4. Abra **Comparação GZ** para consultar o resultado inicial. Para fazer cada estudo do enunciado, volte a **Cargas e tanques**, duplique a condição de referência, selecione a cópia e altere os dados. Para transferir líquido, use o inventário já aplicado e escolha os tanques de origem e destino.
5. Selecione as condições que deseja comparar e exporte as curvas em CSV ou os resultados em Excel. Use **Salvar ou abrir projeto** na barra lateral para baixar um JSON e recuperar os dados em outra sessão.
6. Em **Validação**, consulte os ensaios analíticos com prismas ou carregue uma curva externa para comparar com uma condição sua.

## Importar a geometria de um arquivo

| Origem | Como importar |
|---|---|
| Rhino 3DM | Selecione o arquivo e os objetos do costado. O app lê objetos de malha e faces com malha de renderização gravada. Para uma superfície sem malha gravada ou um bloco, gere a malha do casco no Rhino com `_Mesh` e exporte a seleção em STL ou OBJ. |
| STL ou OBJ | Envie apenas o casco. Verifique unidade, eixos e plano de centro. Para meio casco, selecione o bordo correspondente. O outro bordo é obtido por simetria. |
| Excel e OpenDocument | São aceitos XLSX, XLS, XLSM, XLSB, modelos XLT/XLTX/XLTM e ODS. Escolha a aba das cotas. Em arquivos protegidos por senha, salve uma cópia desprotegida. Para células calculadas por fórmulas, recalcule e salve o arquivo com os valores no Excel. |
| CSV, TSV ou TXT | Envie uma tabela delimitada por ponto e vírgula, vírgula, tabulação ou barra vertical. A leitura aceita números com vírgula decimal. |

**Para uma planilha com cabeçalhos diferentes**, abra “Ver células e números das linhas”. Em “Configurar leitura manualmente”, indique a organização, a primeira e a última linha do bloco de dados. Assim você pode ignorar títulos, observações e totais. Em tabelas com três colunas, associe a posição longitudinal X, a altura Z e a largura. Em matrizes com balizas ou alturas nas linhas, selecione o eixo da primeira coluna e as colunas com larguras. As posições físicas do outro eixo podem vir de uma linha ou ser digitadas na ordem das colunas.

Confira as unidades de X, Z e largura separadamente. Indique se os valores transversais são meias-bocas, bocas totais ou coordenadas Y medidas a partir da linha de centro. Para lacunas, o padrão solicita revisão da célula. Também é possível interpolar dentro de cada baliza entre alturas conhecidas ou assumir zero de forma explícita. Identificadores de baliza e números de linha d’água precisam das posições físicas correspondentes.

**Para um arquivo 3D**, X passa a iniciar na primeira extremidade do eixo longitudinal escolhido e Z inicia no ponto mais baixo. Use o mesmo referencial nos pesos e tanques. A malha é amostrada nas balizas e alturas configuradas, com fechamento na cota indicada. No modelo completo, o leitor verifica nas posições amostradas se existem bordos únicos em lados opostos da linha de centro e se a diferença entre suas meias-bocas está dentro de 1% da boca total. Cascos assimétricos, multicascos e superfícies com mais de um contorno por bordo exigem outro modelo hidrostático. Uma malha mais fina de balizas e alturas ajuda a representar extremos curvos.

**Antes de aplicar**, confira comprimento, boca, altura, volume fechado e algumas seções na prévia. Clique em **Aplicar novo casco** para gerar as curvas KN. O programa só troca o estudo ativo quando os cálculos terminam. Para recuperar o estudo em outra sessão, salve o JSON. Em **Tabela de cotas do casco ativo**, os botões de download fornecem modelos em Excel e CSV.

## Entradas e unidades

- Para calcular KN, informe as seções do casco e a altura de fechamento estanque. Use as unidades e a origem do seu levantamento ao cadastrar as cargas.
- Pesos em t, densidades em t/m³, posições e braços em m, inclinante em t·m (momento de massa, multiplicar por g para obter kN·m), áreas em m·rad. A primeira linha de pesos pode representar a embarcação leve com seus centros iniciais. Os líquidos são cadastrados apenas em tanques.
- Para a comparação externa, carregue a planilha da curva GZ, escolha a aba, as linhas, a coluna de banda em graus, a coluna de GZ e a unidade de comprimento. A convenção é banda positiva para boreste. As diferenças percentuais ficam vazias quando a referência vale zero.
- O formulário aplica uma operação completa por vez. Uma edição inválida apresenta o motivo e preserva o último inventário válido. As alterações da sessão podem ser salvas em JSON antes de fechar a página ou trocar de casco.

## Modelo e limites

A geometria entre linhas d’água é linear. A integração longitudinal usa a regra dos trapézios. Para cada volume e banda, o nível do plano d’água é obtido por bisseção até conservar o volume. A projeção horizontal de B no plano adernado fornece KN. A malha usa bandas de −100° a +100° em passos de 2°. Cada casco novo gera uma malha com 31 volumes entre 3% e 97% do volume fechado. A interpolação é linear em volume, equivalente à interpolação em deslocamento para uma densidade fixa.

A superfície livre inicial usa a soma de ρ·L·B³/12 dos tanques parcialmente cheios dividida pela massa deslocada. Para GZ em grandes ângulos, cada tanque retangular é recortado à banda considerada para localizar o centro real do líquido em equilíbrio estático. A correção de GM e o deslocamento do líquido têm aplicações distintas nas rotinas. A curva com líquido imobilizado mantém massa e centro inicial de líquido iguais.

O modelo admite equilíbrio longitudinal próximo de águas parelhas. Uma estimativa linear de trim acima de 1° em módulo bloqueia o cálculo. Esse limite é didático. O modelo mantém trim fixo nas bandas calculadas. O casco fecha na última cota. Sem dados de aberturas, o gráfico mostra a resposta intacta idealizada. Quando conhecidos, insira limites de alagamento válidos para as condições comparadas. A área fica indisponível se o intervalo definido ultrapassar esses limites. Zeros e máximos dependem da resolução de banda. Um zero tangencial entre amostras pode escapar à detecção. As cargas são pontos; os limites de dimensão de volumes sólidos e os percursos físicos de movimentação requerem informações de arranjo. Não há modelagem dinâmica, de alagamento progressivo ou verificação de critérios regulamentares.

## Material do estudo anterior (consulta opcional)

O relatório em PDF e os arquivos das pastas `dados` e `validacao` documentam os exemplos que acompanhavam o projeto original. Os valores do seu novo estudo são gerados na sessão a partir dos dados que você inserir.

Cotas do Damen em `hydrostatic_table (1)(1).xlsx`, aba **Tabela de trabalho**, derivadas de `Cotas_damen01.xlsx`. Comprimento entre as balizas extremas de 19,190 m, fechamento no pontal de 2,70 m. O arquivo de trabalho possui cotas superiores até 3,00 m. As seções foram interpoladas até o pontal e fechadas nesse nível.

Pesos e capacidades de referência da condição `condicao_C6_operacional_equilibrada.xlsx` do AP1.3. Os centros dos sólidos, massas e capacidade dos dois tanques originais foram preservados. Adotaram-se Y inicial nulo, fundo do tanque de combustível em 0,85 m, fundo dos tanques de água em 0,65 m e X dos tanques de água em 8,60 e 10,70 m. O segundo tanque de água é auxiliar e inicia vazio. Essas posições idealizadas respeitam a envoltória das cotas e evitam superposição. Os estudos, a validação e os limites constam no PDF que acompanha o código.

## Arquivos e reprodução

| Arquivo | Conteúdo |
|---|---|
| app.py | Interface, gráficos, seleção de condições e exportações |
| geometria.py | Integração hidrostática, curvas cruzadas e equilíbrio de volume |
| estabilidade.py | Centro de gravidade, GM, líquido móvel e indicadores de GZ |
| cenarios.py | Seis inventários iniciais e transferência de líquido |
| entrada.py / importador.py / cad.py | Formatos de planilha, mapeamento, seções de malha CAD e prévia |
| projeto.py | Persistência do estudo |
| dados/damen.csv / cruzadas_damen.npz | Cotas e malha KN do estudo anterior |
| dados/estudos_AP15.json | Projeto arquivado que pode ser importado por escolha do usuário |
| dados/curvas.csv / indicadores.csv / intervalos.csv | Seis casos, duas distâncias adicionais e dois ensaios de alteração de massa |
| validacao/ | Balanço manual, cinco braços GZ, teste de Tupper e comparação hidrostática com a AP anterior |

Execute `python estudos.py` para reproduzir as tabelas dos estudos, `python verificacao.py` para reproduzir os controles analíticos e `python testes.py` para verificar cenários, conservação, limites e gravação de projeto. A referência técnica da segunda validação é E. C. Tupper, *Introduction to Naval Architecture*, 3ª ed., 1996, cap. 4, p. 61. O teste usa apenas a faixa em que a linha d’água intercepta ambos os costados verticais. Os resultados da validação são de referência bibliográfica.

Para reconstruir a malha do Damen a partir das cotas, execute `python malha.py`. Esse script reproduz o estudo arquivado.
