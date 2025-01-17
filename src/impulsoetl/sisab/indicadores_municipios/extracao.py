# SPDX-FileCopyrightText: 2021, 2022 ImpulsoGov <contato@impulsogov.org>
#
# SPDX-License-Identifier: MIT


"""Extrai dados de indicadores de desempenho a partir do SISAB."""

from __future__ import annotations

from datetime import date
from io import StringIO
from typing import Final

import pandas as pd
import requests

from impulsoetl.loggers import logger
from impulsoetl.sisab.parametros_requisicao import head

INDICADORES_CODIGOS: Final[dict[str, str]] = {
    "Pré-Natal (6 consultas)": "10",
    "Pré-Natal (Sífilis e HIV)": "20",
    "Gestantes Saúde Bucal": "30",
    "Cobertura Citopatológico": "40",
    "Cobertura Polio e Penta": "50",
    "Hipertensão (PA Aferida)": "60",
    "Diabetes (Hemoglobina Glicada)": "70",
}

VISOES_EQUIPE_CODIGOS: Final[dict[str, str]] = {
    "todas-equipes": "",
    "equipes-homologadas": "|HM|",
    "equipes-validas": "|HM|NC|",
}


def verifica_colunas(df_extraido: pd.DataFrame) -> int:
    """Verifica se 'Dataframe' possui 13 colunas como esperado"""
    return df_extraido.shape[1]


def verifica_linhas(df_extraido: pd.DataFrame) -> int:
    """Verifica se 'Dataframe' possui mais do que 5000 registros como esperado"""
    return df_extraido.shape[0]


def extrair_indicadores(
    indicador: str,
    visao_equipe: str,
    quadrimestre: date,
    url=(
        "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal"
        + "/indicadores/indicadorPainel.xhtml"
    ),
) -> str:
    """Extrai relatório de indicadores do SISAB.

    Argumentos:
        indicador: Nome do indicador.
        visao_equipe: Status da equipe de saúde .
        quadrimestre: Data do quadrimestre da competência de referência

    Retorna:
        Um objeto `pandas.DataFrame` com dados capturados pela requisição.
    """

    # NOTE: a função `head()` captura cookies da página web do relatório
    hd = head(url)
    vs = hd[1]
    payload = (
        "j_idt51=j_idt51"
        "&coIndicador="
        + INDICADORES_CODIGOS[indicador]
        + "&selectLinha=ibge"
        + "&estadoMunicipio="
        + "&quadrimestre={:%Y%m}".format(quadrimestre)
        + "&visaoEquipe="
        + VISOES_EQUIPE_CODIGOS[visao_equipe]
        + "&javax.faces.ViewState="
        + vs
        + "&j_idt87=j_idt87"
    )
    headers = hd[0]
    logger.info("Iniciando extração do relatório...")
    response = requests.request(
        "POST", url,
        headers=headers,
        data=payload,
        timeout=120,
    )
    df_extraido = pd.read_csv(
        StringIO(response.text),
        delimiter=";",
        header=10,
        encoding="ISO-8859-1",
    )
    df_extraido = df_extraido.drop(
        ["UF", "Munícipio", "Unnamed: 12"],
        axis=1,
    ).dropna()
    assert verifica_colunas(df_extraido=df_extraido) == 10
    assert verifica_linhas(df_extraido=df_extraido) > 5000
    logger.info(
        "Extração dos relatório realizada | Total de registros : {registros}",
        registros=df_extraido.shape[0],
    )

    return df_extraido
