
import requests
from suporte_extracao import head
from io import StringIO
import pandas as pd
import os
import json
import dotenv
from datetime import datetime
import uuid

dotenv.load_dotenv(dotenv.find_dotenv())
oge = os.getenv

# ----------- importações para consulta banco
from sqlalchemy import create_engine
import psycopg2
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

# ----------- importações para carga
from impulsoetl.loggers import logger
from impulsoetl.bd import tabelas

# importacao para transformacao

from impulsoetl.comum.geografias import id_sus_para_id_impulso
from frozenlist import FrozenList


# conexão com banco de dados                 #postgres://usuario:senha@host:porta(5432)/database

engine = create_engine(
    f"postgresql+psycopg2://{oge('IMPULSOETL_BD_USUARIO')}:{oge('IMPULSOETL_BD_SENHA')}@{oge('IMPULSOETL_BD_HOST')}:{oge('IMPULSOETL_BD_PORTA')}/{oge('IMPULSOETL_BD_NOME')}"
)
conn = engine.raw_connection()
cur = conn.cursor()

Session = sessionmaker(bind=engine)
sessao = Session()


# teste de conexão -
try:
    conn
    logger.info("Conexão com o banco Impulso OK!")
except Exception as e:
    logger.info("connect fail : ")






# Agendamento

# agendamentos = tabelas["configuracoes.capturas_agendamentos"]
# operacao_id = "c84c1917-4f57-4592-a974-50a81b3ed6d5"
# agendamentos_validacao_municipio_producao = (
#     sessao.query(agendamentos)
#     .filter(agendamentos.c.operacao_id == operacao_id)
#     .all()
# )

# for agendamento in agendamentos_validacao_municipio_producao:
#         periodos_list = []
#         periodos_list.append(agendamento.periodo_data_inicio.strftime('%Y%m'))
        

agendamentos = tabelas["configuracoes.capturas_agendamentos"]
operacao_id = ('c84c1917-4f57-4592-a974-50a81b3ed6d5')

periodos = pd.read_sql_query(
        f"""select distinct periodo_data_inicio from {agendamentos} where operacao_id = '{operacao_id}';""",
        engine,
    )

periodos['periodo_data_inicio'] = pd.to_datetime(periodos['periodo_data_inicio'])

periodos["periodo_data_inicio"] = periodos["periodo_data_inicio"].apply(lambda x: (x).strftime('%Y%m'))

#periodos_lista = periodos['periodo_data_inicio'].tolist()

# Unidade geográfica
unidade_geografica_query = pd.read_sql_query(
    f"""select distinct unidade_geografica_id  from {agendamentos} where operacao_id = '{operacao_id}';""", engine)

unidade_geografica_query['unidade_geografica_id'] = unidade_geografica_query['unidade_geografica_id'].astype("string")

unidade_geografica_query_list = unidade_geografica_query['unidade_geografica_id'].tolist()



def id_unidade_geografica_para_nome (
    unidade_geografica_id
):
    tb_unidade_geografica = tabelas["listas_de_codigos.unidades_geograficas"]
    id_para_nome = pd.read_sql_query(
    f"""select nome from {tb_unidade_geografica} where id = '{unidade_geografica_id}';""", engine)
    id_para_nome = id_para_nome.iloc[0]

    return id_para_nome


unidade_geografica_query['unidade_geografica'] = unidade_geografica_query['unidade_geografica_id'].apply(lambda x: id_unidade_geografica_para_nome(x))
unidade_geografica_query_list = unidade_geografica_query['unidade_geografica_id'].tolist()



# -------------------------------------------Extração-----------------------------------


"""

    Faz a extração do relatório de validação de acordo com alguns parâmetros 

"""
# Checando disponibilidade da API
try:
    url = "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/envio/RelValidacao.xhtml"
    retorno = requests.get(url)  # checagem da URl
    logger.info("Api Online ")
except Exception as e:
    logger.info("Erro na requisição: ")


# Filtros dos períodos no sisab website
periodo_tipo = "producao"  # produção ou envio


periodo_competencia = "202203"  # AAAAMM periodo averiguado
#periodo_competencia = periodos_lista

"""
    Pelo padrão utilizado no banco de dados da impulso e dos dados obtidos mensalmente, fazer a conversão de AAAAMM para AAAAMX onde X é o mês de competência 

"""

ano = periodo_competencia[0:4]

mes = ".M" + periodo_competencia[5:6]

periodo_codigo = ano + mes

envio_prazo_on = (
    "&envioPrazo=on"  # Check box envio requisições no prazo marcado
)

envio_prazo = (
    []
)  # preencher envio_prazo_on ou deixar vazio ou usar '' em caso de querer os 2 de uma vez

aplicacao = []  # tipo de aplicação Filtro 4

# # ---------------Busca dados na API SISAB relatório validacao
# try:
#     hd = head(url)
#     vs = hd[1]  # viewstate
#     payload = (
#         "j_idt44=j_idt44&unidGeo=brasil&periodo="
#         + periodo_tipo
#         + "&j_idt70="
#         + periodo_competencia
#         + "&colunas=regiao&colunas=uf&colunas=ibge&colunas=municipio&colunas=cnes&colunas=ine&javax.faces.ViewState="
#         + vs
#         + "&j_idt102=j_idt102"
#     )
#     headers = hd[0]
#     response = requests.request("POST", url, headers=headers, data=payload)
#     logger.info("Dados obtidos")

# except Exception as e:
#     logger.info(e)
#     logger.info("leitura falhou")


# --------------------------------------------TRATAMENTO

# leitura do arquivo pulando o cabeçalho e últimas linhas
"""
    TRATAMENTO DE DADOS
    Dados excluídos por falta de necessidade: Região, Uf, Município, coluna NaN
    Coluna IBGE e demais colunas mudarão de nome 
"""
try:

#     df = pd.read_csv(
#         StringIO(response.text),
#         sep=";",
#         encoding="ISO-8859-1",
#         engine="python",
#         skiprows=range(0, 4),
#         skipfooter=4,
#     )  # ORIGINAL DIRETO DA EXTRAÇÃO

    # execução local
    df = pd.read_csv ('/home/silas/Documentos/Impulso/etlValidacaolocal/rel_Validacao032022.csv',sep=';',encoding = 'ISO-8859-1',engine='python', skiprows=range(0,4), skipfooter=4)

    logger.info("Dados carregados!!!")

except Exception as e:
    logger.info(+" Falha no carregamento")


logger.info("Dados em tratamento!")

try:

#     df = pd.read_csv(
#         StringIO(response.text),
#         sep=";",
#         encoding="ISO-8859-1",
#         engine="python",
#         skiprows=range(0, 4),
#         skipfooter=4,
#     )  # ORIGINAL DIRETO DA EXTRAÇÃO

    # execução local
    df = pd.read_csv ('/home/silas/Documentos/Impulso/etlValidacaolocal/rel_Validacao032022.csv',sep=';',encoding = 'ISO-8859-1',engine='python', skiprows=range(0,4), skipfooter=4)

    logger.info("Dados carregados!!!")

except Exception as e:
    logger.info(+" Falha no carregamento")


logger.info("Dados em tratamento!")

try:

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
        criacao_data=pd.Timestamp.now(),
        atualizacao_data=pd.Timestamp.now(),
        no_prazo=1 if (envio_prazo == envio_prazo_on) else 0,
        periodo_codigo=periodo_codigo,
    )

    query = pd.read_sql_query(
        f"select id  from listas_de_codigos.periodos where codigo  = '{periodo_codigo}';",
        engine,
    )

    query = query.iloc[0]["id"]

    df = df.assign(periodo_id=query)

    idsus = df.iloc[0][
        "municipio_id_sus"
    ]  # idsus para preencher coluna id_unidade_geo

    id_unidade_geo = id_sus_para_id_impulso(sessao, idsus)

    df = df.assign(unidade_geografica_id=id_unidade_geo)

    df['id'] = df.apply(lambda row:uuid.uuid4(), axis=1)
    
    df["id"] = df["id"].astype("string")

    df["municipio_id_sus"] = df["municipio_id_sus"].astype("string")

    df["periodo_id"] = df["periodo_id"].astype("string")

    df["cnes_id"] = df["cnes_id"].astype("string")

    df["ine_id"] = df["ine_id"].astype("string")

    df["validacao_nome"] = df["validacao_nome"].astype("string")

    df["validacao_quantidade"] = df["validacao_quantidade"].astype("int")

    df["periodo_codigo"] = df["periodo_codigo"].astype("string")

    df["unidade_geografica_id"] = df["unidade_geografica_id"].astype("string")

    df["no_prazo"] = df["no_prazo"].astype("bool")
    
    df['criacao_data'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    df['atualizacao_data'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("Dados Tratados!")
    logger.info("Dataframe final Pronto!")
    
except Exception as e:
    logger.info(" Erro de tratamento!")


print(df.head())
# ------------------------------------------------------------------------------------------
# def carregar_relatorio_validacao(
#     sessao: Session, relatorio_validacao_df: pd.DataFrame
# ) -> int:
#     """Carrega os dados de um arquivo validação do portal SISAB no BD da Impulso.

#     Argumentos:
#         sessao: objeto [`sqlalchemy.orm.session.Session`][] que permite
#             acessar a base de dados da ImpulsoGov.
#         relatorio_validacao_df: [`DataFrame`][] contendo os dados a serem carregados
#             na tabela de destino, já no formato utilizado pelo banco de dados
#             da ImpulsoGov.

#     Retorna:
#         Código de saída do processo de carregamento. Se o carregamento
#         for bem sucedido, o código de saída será `0`.

#     """

relatorio_validacao_df = df

registros = json.loads(
    relatorio_validacao_df.to_json(
        orient="records",
        date_format="iso",
    )
)


tabela_relatorio_validacao = tabelas[
    "dados_publicos._sisab_validacao_municipios_por_producao"
]  # tabela teste

requisicao_insercao = tabela_relatorio_validacao.insert().values(registros)

try:
    conector = sessao.connection()
    conector.execute(requisicao_insercao)

    
    logger.info(
        "Carregamento concluído para a tabela `{tabela_nome}`: "
        + "adicionadas {linhas_adicionadas} novas linhas.",
        tabela_nome="dados_publicos._sisab_validacao_municipios_por_producao",  
        linhas_adicionadas=len(relatorio_validacao_df))
    

except Exception as e:
    logger.info(e)












#

# Análise dos dados
# df.head(10)
#
# df.tail(10)
#
# print(df)
#
# df.isnull().sum()

# códigos para checagem de tipo e conteúdo do request
# print(type(response))
# src = response.content
# src
