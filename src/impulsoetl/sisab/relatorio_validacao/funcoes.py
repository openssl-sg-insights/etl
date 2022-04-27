# SPDX-FileCopyrightText: 2021, 2022 ImpulsoGov <contato@impulsogov.org>
#
# SPDX-License-Identifier: MIT


import requests
from impulsoetl.sisab.relatorio_validacao.suporte_extracao import head
from io import StringIO
import pandas as pd
import os
import json
import dotenv
from datetime import datetime
import uuid
# ----------- importações para consulta banco
from sqlalchemy import create_engine
import psycopg2
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
#----------- importações para carga
from impulsoetl.loggers import logger
from impulsoetl.bd import tabelas
# importacao para transformacao
from impulsoetl.comum.geografias import id_sus_para_id_impulso
from frozenlist import FrozenList
from impulsoetl.bd import Sessao

def obter_lista_periodos_inseridos(sessao):
    """Obtém lista de períodos da períodos que já constam na tabela

        Returns:
        periodos_lista: períodos que já constam na tabela destino
    """    

    
    engine = sessao.get_bind()
    tabela_alvo="dados_publicos._sisab_validacao_municipios_por_producao"
    periodos = pd.read_sql_query(
            f"""select distinct periodo_codigo from {tabela_alvo};""",
            engine    )
    periodos = periodos['periodo_codigo'].tolist()
    logger.info("Leitura dos períodos inseridos no banco Impulso OK!")
    return periodos

def competencia_para_periodo_codigo(periodo_competencia):
    """Essa função converte o período de competência de determinado relatorio no código do periodo padrão da impulso
    EX: 202203 para 2022.M3
    Args:
        periodo_competencia (str): período de competência de determinado relatório

    Returns:
        periodo código
    """


    ano = periodo_competencia[0:4]
    mes = ".M" + periodo_competencia[4:6]
    if mes[2] == '0':
        mes = ".M" + periodo_competencia[5:6]
        periodo_codigo = ano + mes
    else:
        periodo_codigo = ano + mes
    return periodo_codigo

def obter_data_criacao(sessao,tabela, periodo_codigo):
    """Obtém a data de criação do registro que já consta na tabela baseado no período
        
        Args:
            tabela (str): tabela alvo da busca
            periodo_codigo (str): Período de referência da data
        
        Returns:
        data_criacao: data em formato datetime  
    """

    
    engine = sessao.get_bind()
    data_criacao = pd.read_sql_query(
                f"select distinct criacao_data from {tabela} where periodo_codigo  = '{periodo_codigo}';",
                engine)
    if data_criacao.empty == True:
        data_criacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    else:
        data_criacao = data_criacao.iloc[0]["criacao_data"].strftime("%Y-%m-%d %H:%M:%S")
    return data_criacao



def requisicao_validacao_sisab_producao(periodo_competencia,envio_prazo):
    """Obtém os dados da API
    
    Args:
        periodo_competencia: Período de competência do dado a ser buscado no sisab
        envio_prazo(bool): Tipo de relatório de validação a ser obtido (referência check box "no prazo" no sisab)  
    
    Returns:
    resposta: Resposta da requisição do sisab, com os dados obtidos ou não
    """

    
    url = "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/envio/RelValidacao.xhtml"
    periodo_tipo='producao'
    hd = head(url)
    vs = hd[1] #viewstate
    payload='j_idt44=j_idt44&unidGeo=brasil&periodo='+periodo_tipo+'&j_idt70='+periodo_competencia+'&colunas=regiao&colunas=uf&colunas=ibge&colunas=municipio&colunas=cnes&colunas=ine'+envio_prazo+'&javax.faces.ViewState='+vs+'&j_idt102=j_idt102'
    headers = hd[0]
    resposta = requests.request("POST", url, headers=headers, data=payload)
    logger.info("Dados Obtidos no SISAB")
    return resposta

def tratamento_validacao_producao(sessao,resposta,data_criacao,envio_prazo,periodo_codigo):
    """Tratamento dos dados obtidos 

    Args:
    resposta (requests.models.Response): Resposta da requisição efetuada no sisab


    Returns:
    df: dataframe com os dados enriquecidos e tratados em formato pandas dataframe  
    """
    
    
    logger.info("Dados em tratamento")
    engine = sessao.get_bind()
    envio_prazo_on = '&envioPrazo=on'

    df = pd.read_csv(StringIO(resposta.text),sep=';',encoding = 'ISO-8859-1', skiprows=range(0,4), skipfooter=4,  engine='python') #ORIGINAL DIRETO DA EXTRAÇÃO 

    df['INE'] = df['INE'].fillna('0')

    df['INE'] = df['INE'].astype('int')

    assert df['Uf'].count() > 26, "Estado faltante"

    df.drop(["Região", "Uf", "Municipio", "Unnamed: 8"], axis=1, inplace=True)

    df.columns = [
        "municipio_id_sus",
        "cnes_id",
        "ine_id",
        "validacao_nome",
        "validacao_quantidade",
    ]

    # ------------- novas colunas em lugares específicos
    df.insert(0, "id", value="")

    df.insert(2, "periodo_id", value="")
    
    # -------------novas colunas para padrão tabela requerida

    df = df.assign(
        criacao_data=data_criacao,
        atualizacao_data=pd.Timestamp.now(),
        no_prazo=1 if (envio_prazo == envio_prazo_on) else 0,
        periodo_codigo=periodo_codigo,
    )

    periodo_id = pd.read_sql_query(
        f"select id  from listas_de_codigos.periodos where codigo  = '{periodo_codigo}';",
        engine,
    )
    
    periodo_id = periodo_id.iloc[0]["id"]

    df = df.assign(periodo_id=periodo_id)

    df['id'] = df.apply(lambda row:uuid.uuid4(), axis=1)
    
    df.insert(11, "unidade_geografica_id", value="")
    
    df['unidade_geografica_id'] = df['municipio_id_sus'].apply(lambda row: id_sus_para_id_impulso(sessao, id_sus=row))

    df[["id","municipio_id_sus", "periodo_id","cnes_id",\
        "ine_id","validacao_nome","periodo_codigo","unidade_geografica_id"]] = df[["id","municipio_id_sus", "periodo_id","cnes_id","ine_id",\
        "validacao_nome","periodo_codigo","unidade_geografica_id"]].astype("string")


    df["validacao_quantidade"] = df["validacao_quantidade"].astype("int")

    df["no_prazo"] = df["no_prazo"].astype("bool")

    df['atualizacao_data'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    df_validacao_tratado = df 
    logger.info("Dados tratados")
    print(df_validacao_tratado.head())
    return df_validacao_tratado

def carregar_validacao_producao(sessao,df_validacao_tratado,periodo_competencia,tabela_destino):
    """Carrega os dados de um arquivo validação do portal SISAB no BD da Impulso.

    Argumentos:
        sessao: objeto [`sqlalchemy.orm.session.Session`][] que permite
            acessar a base de dados da ImpulsoGov.
        relatorio_validacao_df: [`DataFrame`][] contendo os dados a serem carregados
            na tabela de destino, já no formato utilizado pelo banco de dados
            da ImpulsoGov.

    Retorna:
        Código de saída do processo de carregamento. Se o carregamento
        for bem sucedido, o código de saída será `0`.
     """

    
    engine = sessao.get_bind()
    relatorio_validacao_df = df_validacao_tratado

    registros = json.loads(
        relatorio_validacao_df.to_json(
            orient="records",
            date_format="iso",
        )
    )

    
    tabela_relatorio_validacao = tabelas[tabela_destino]

    conector = sessao.connection()

    periodo_codigo = competencia_para_periodo_codigo(periodo_competencia)

    periodos_inseridos = obter_lista_periodos_inseridos(sessao)

    if periodo_codigo in periodos_inseridos:
        
        limpar = delete(tabela_relatorio_validacao).where(tabela_relatorio_validacao.c.periodo_codigo == periodo_codigo)
        print(limpar)
        conector.execute(limpar)
        



    requisicao_insercao = tabela_relatorio_validacao.insert().values(registros)
    print(requisicao_insercao)

    conector.execute(requisicao_insercao)
    
    
    logger.info(
    "Carregamento concluído para a tabela `{tabela_nome}`: "
    + "adicionadas {linhas_adicionadas} novas linhas.",
    tabela_nome="dados_publicos._sisab_validacao_municipios_por_producao", 
    linhas_adicionadas=len(relatorio_validacao_df))
    
    return 0

def testes_pre_carga (df_validacao_tratado):
    """Realiza algumas validações no dataframe antes da carga ao banco.

    Argumentos:
            relatorio_validacao_df: [`DataFrame`][] contendo os dados a serem carregados
            na tabela de destino, já no formato utilizado pelo banco de dados
            da ImpulsoGov.

    Retorna:
        Código de saída do processo de carregamento. Se o carregamento
        for bem sucedido, o código de saída será `0`.
    """


    assert df_validacao_tratado['municipio_id_sus'].nunique() > 5000, "Número de municípios obtidos menor que 5000"

    assert df_validacao_tratado['unidade_geografica_id'].nunique() == df_validacao_tratado['municipio_id_sus'].nunique() , "Falta de unidade geográfica"

    assert sum(df_validacao_tratado['cnes_id'].isna()) == 0, "Dado ausente em cnes_id"

    assert sum(df_validacao_tratado['id'].isna()) == 0, "Id do registro ausente"

    assert sum(df_validacao_tratado['validacao_nome'].isna()) == 0, "Nome da validacão ausente"

    assert sum(df_validacao_tratado['validacao_quantidade']) > 0, "Quantidade de validação inválida"
    
    assert len(df_validacao_tratado.columns) == 12, "Falta de coluna no dataframe"

    logger.info("Testes OK!")


def obter_validacao_municipios_producao(sessao,periodo_competencia,envio_prazo,tabela_destino,periodo_codigo):
    """Executa a Extração, Transformação e Carga para memória utilizando as funções próprias para isso.

    Argumentos:
        periodo_competencia: Período de competência do dado, obtido no script impulso_previne
        envio_prazo: No prazo sim ou não, obtido no script impulso_previne

    Retorna:
        Código de saída do processo de carregamento. Se o carregamento
        for bem sucedido, o código de saída será `0`.
  """


    data_criacao = obter_data_criacao(sessao,tabela_destino,periodo_codigo)

    resposta = requisicao_validacao_sisab_producao(periodo_competencia,envio_prazo)

    df_validacao_tratado = tratamento_validacao_producao(sessao,resposta,data_criacao,envio_prazo,periodo_codigo)

    testes_pre_carga (df_validacao_tratado)

    carregar_validacao_producao(sessao,df_validacao_tratado,periodo_competencia,tabela_destino)
    logger.info("Dados prontos para o commit")



            