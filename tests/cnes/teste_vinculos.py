# SPDX-FileCopyrightText: 2021, 2022 ImpulsoGov <contato@impulsogov.org>
#
# SPDX-License-Identifier: MIT


"""Casos de teste para o ETL de dados de vínculos profissionais do CNES."""


import re

import pandas as pd
import pytest

from impulsoetl.bd import tabelas
from impulsoetl.cnes.vinculos import (
    COLUNAS_DATA_AAAAMM,
    DE_PARA_VINCULOS,
    TIPOS_VINCULOS,
    obter_vinculos,
    transformar_vinculos,
)
from impulsoetl.utilitarios.bd import carregar_dataframe


@pytest.fixture(scope="module")
def _vinculos():
    return pd.read_parquet("tests/cnes/CNES_PFSE2111_.parquet")


@pytest.fixture(scope="function")
def vinculos(_vinculos):
    return _vinculos.copy()


@pytest.fixture(scope="module")
def _vinculos_transformado():
    return pd.read_parquet("tests/cnes/vinculos_transformado.parquet")


@pytest.fixture(scope="function")
def vinculos_transformado(_vinculos_transformado):
    return _vinculos_transformado.copy()


@pytest.fixture(scope="function")
def tabela_teste(sessao):
    try:
        # copiar estrutura da tabela original
        sessao.execute(
            "create table "
            + "dados_publicos._cnes_vinculos_disseminacao ("
            + "like dados_publicos.cnes_vinculos_disseminacao "
            + "including all"
            + ");",
        )
        sessao.commit()
        yield "dados_publicos._cnes_vinculos_disseminacao"
    finally:
        sessao.rollback()
        sessao.execute(
            "drop table if exists "
            + "dados_publicos._cnes_vinculos_disseminacao;",
        )
        sessao.commit()


def teste_de_para(vinculos):
    colunas_origem = [col.strip() for col in vinculos.columns]
    colunas_de = list(DE_PARA_VINCULOS.keys())

    for col in colunas_de:
        assert col in colunas_origem, (
            "Coluna no De-Para não existe no arquivo de procedimentos: "
            + "'{}'".format(col)
        )
    for col in colunas_origem:
        assert col in colunas_de, (
            "Coluna existente no arquivo de procedimentos não encontrada no "
            + "De-Para: '{}'".format(col)
        )


def teste_tipos(vinculos):
    tabela_destino = tabelas["dados_publicos.cnes_vinculos_disseminacao"]
    colunas_destino = tabela_destino.columns

    for col in TIPOS_VINCULOS.keys():
        assert (
            col in colunas_destino
        ), "Coluna inexistente na tabela de destino: '{}'".format(col)
    for col in colunas_destino.keys():
        assert col in TIPOS_VINCULOS, "Coluna sem tipo definido: '{}'".format(
            col
        )


def teste_colunas_datas():
    assert all(col in TIPOS_VINCULOS.keys() for col in COLUNAS_DATA_AAAAMM)


@pytest.mark.integracao
def teste_transformar_vinculos(sessao, vinculos):
    vinculos_transformado = transformar_vinculos(
        sessao=sessao,
        vinculos=vinculos,
    )

    assert isinstance(vinculos_transformado, pd.DataFrame)
    assert len(vinculos_transformado) > 1

    colunas_processadas = vinculos_transformado.columns
    colunas_esperadas = list(TIPOS_VINCULOS.keys())
    for col in colunas_processadas:
        assert re.match(
            "[a-z_]+", col
        ), "Caracteres proibidos no nome da coluna '{}'".format(col)
        assert (
            col in colunas_esperadas
        ), "Coluna '{}' não definida na tabela de destino.".format(col)
        if "data" in col:
            assert (
                str(vinculos_transformado[col].dtype) == "datetime64[ns]"
            ), "Coluna de data com tipo incorreto: '{}'".format(col)

    for col in colunas_esperadas:
        assert col in colunas_esperadas, "Coluna não encontrada: '{}'.".format(
            col
        )


def teste_carregar_vinculos(
    sessao,
    vinculos_transformado,
    tabela_teste,
    caplog,
):
    carregamento_status = carregar_dataframe(
        sessao=sessao,
        df=vinculos_transformado.iloc[:10],
        tabela_destino=tabela_teste,
        passo=10,
        teste=True,
    )

    assert carregamento_status == 0

    logs = caplog.text
    assert "Carregamento concluído" in logs


@pytest.mark.integracao
@pytest.mark.parametrize(
    "uf_sigla",
    ["SE"],
)
@pytest.mark.parametrize(
    "ano,mes",
    [(2021, 8)],
)
def teste_obter_vinculos(sessao, uf_sigla, ano, mes, tabela_teste, caplog):
    obter_vinculos(
        sessao=sessao,
        uf_sigla=uf_sigla,
        ano=ano,
        mes=mes,
        tabela_destino=tabela_teste,
        teste=True,
    )

    logs = caplog.text
    assert "Carregamento concluído" in logs
