
import requests
import urllib
from sisab.parametros_requisicao import head
import pandas as pd
from io import StringIO
from impulsoetl.tipos import DatetimeLike
 

def extrair_parametros_equipes(visao_equipe:str,competencia:DatetimeLike)->str:
    competencia = competencia.replace('-','')
    competencia= competencia[0:6]
    url = "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/indicadores/indicadorCadastro.xhtml"
    hd = head(url)
    vs = hd[1]
    ponderacao = ''
    visao_equipe = urllib.parse.quote(visao_equipe)
    headers = hd[0]
    payload='j_idt44=j_idt44&selectLinha=cnes_ine&opacao-capitacao='+visao_equipe+ponderacao+'&competencia='+competencia+'&javax.faces.ViewState='+vs+'&j_idt83=j_idt83'
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.text

def _extrair_parametros_equipes(rp:str)->pd.DataFrame:
 
    df = pd.read_csv(StringIO(rp), delimiter='\t', header=None, engine= 'python')
    dados = df.iloc[9:-4]
    df = pd.DataFrame(data=dados)
    df=df[0].str.split(';', expand=True)
    df.columns=['Uf','IBGE','Municipio','CNES','Nome UBS','INE','Sigla','quantidade','parametro','Coluna']  
    return df

