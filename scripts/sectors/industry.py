# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2020-2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def add_steel(
    n,
    industrial_production,
    costs,
    nodes,
    nhours,
    options,
):
    # original source:
    # https://github.com/PyPSA/pypsa-eur/blob/aab1dd365e2dcbaf5806783f74eb64810f83132f/scripts/prepare_sector_network.py#L3217-L3331

    # we could extend the options for industry.
    # for current documentation see
    # docs in https://pypsa-eur.readthedocs.io/en/latest/configuration.html#industry

    # meanings of some abbreviations used in context of steel sector:
    # DRI: Direct Reduced Iron
    # EAF: Electric Arc Furnaces
    # HBI: Hot Briquetted Iron
    # HBI is a form of direct reduced iron (DRI) that has been
    # compacted into briquettes to facilitate handling, storage, and
    # transportation. HBI is used as a feedstock in electric arc
    # furnaces (EAF) for steel production. It is valued for its
    # high iron content and low levels of impurities, making it
    # an efficient and cleaner alternative to traditional
    # iron sources in steel making.

    options["endogenous_steel"] = True

    if options["endogenous_steel"]:
        logger.info("Adding endogenous primary steel demand in tonnes.")

        _create_steel_buses(n)

        sector = "DRI + Electric arc"
        steel_production = industrial_production[sector]
        _create_steel_load(
            n,
            steel_production,
            nhours,
        )

        no_flexibility, no_relocation = _initialize_options(options)
        if not no_flexibility:
            _create_stores(n)

        _link_nodes_to_hbi_and_h2_buses(
            n,
            steel_production,
            costs,
            nodes,
            nhours,
            no_flexibility,
            no_relocation,
        )

        _link_nodes_to_steel_and_hbi_buses(
            n,
            steel_production,
            costs,
            nodes,
            nhours,
            no_flexibility,
            no_relocation,
        )

    return n


def _create_steel_buses(n):
    n.add(
        "Bus",
        "EU steel",
        location="EU",
        carrier="steel",
        unit="t",
    )
    n.add(
        "Bus",
        "EU HBI",
        location="EU",
        carrier="HBI",
        unit="t",
    )


def _create_steel_load(
    n,
    steel_production,
    nhours,
):
    steel_production_per_hour = steel_production.sum() / nhours
    n.add(
        "Load",
        "EU steel",
        bus="EU steel",
        carrier="steel",
        p_set=steel_production_per_hour,
    )


def _initialize_options(options):
    no_relocation = not options.get("relocation_steel", False)
    no_flexibility = not options.get("flexibility_steel", False)

    s = " not" if no_relocation else " "
    logger.info(f"Steel industry relocation{s} activated.")

    s = " not" if no_flexibility else " "
    logger.info(f"Steel industry flexibility{s} activated.")

    return no_flexibility, no_relocation


def _create_stores(n):
    n.add(
        "Store",
        "EU steel Store",
        bus="EU steel",
        e_nom_extendable=True,
        e_cyclic=True,
        carrier="steel",
    )
    n.add(
        "Store",
        "EU HBI Store",
        bus="EU HBI",
        e_nom_extendable=True,
        e_cyclic=True,
        carrier="HBI",
    )


def _link_nodes_to_hbi_and_h2_buses(
    n,
    steel_production,
    costs,
    nodes,
    nhours,
    no_flexibility,
    no_relocation,
):
    electricity_input = costs.at[
        "direct iron reduction furnace",
        "electricity-input",
    ]

    # so that for each region supply matches consumption
    p_nom = (
        steel_production
        * costs.at["electric arc furnace", "hbi-input"]
        * electricity_input
        / nhours
    )

    capital_cost = (
        costs.at["direct iron reduction furnace", "fixed"] / electricity_input
    )

    marginal_cost = (
        costs.at["iron ore DRI-ready", "commodity"]
        * costs.at["direct iron reduction furnace", "ore-input"]
        / electricity_input
    )

    hbi_efficiency = 1 / electricity_input
    hydrogen_efficiency = _hydrogen_efficiency(costs, electricity_input)

    n.madd(
        "Link",
        nodes,
        suffix=" DRI",
        carrier="DRI",
        capital_cost=capital_cost,
        marginal_cost=marginal_cost,
        p_nom_max=p_nom if no_relocation else np.inf,
        p_nom_extendable=True,
        p_min_pu=1 if no_flexibility else 0,
        bus0=nodes,
        bus1="EU HBI",
        bus2=nodes + " H2",
        efficiency=hbi_efficiency,
        efficiency2=hydrogen_efficiency,
    )


def _hydrogen_efficiency(costs, electricity_input):
    hydrogen_input = costs.at[
        "direct iron reduction furnace",
        "hydrogen-input",
    ]
    hydrogen_efficiency = -hydrogen_input / electricity_input
    return hydrogen_efficiency


def _link_nodes_to_steel_and_hbi_buses(
    n,
    steel_production,
    costs,
    nodes,
    nhours,
    no_flexibility,
    no_relocation,
):
    electricity_input = costs.at[
        "electric arc furnace",
        "electricity-input",
    ]

    capital_cost = costs.at["electric arc furnace", "fixed"] / electricity_input

    p_nom = steel_production * electricity_input / nhours

    steel_efficiency = 1 / electricity_input

    hbi_efficiency = -costs.at["electric arc furnace", "hbi-input"] / electricity_input

    n.madd(
        "Link",
        nodes,
        suffix=" EAF",
        carrier="EAF",
        capital_cost=capital_cost,
        p_nom_max=p_nom if no_relocation else np.inf,
        p_nom_extendable=True,
        p_min_pu=1 if no_flexibility else 0,
        bus0=nodes,
        bus1="EU steel",
        bus2="EU HBI",
        efficiency=steel_efficiency,
        efficiency2=hbi_efficiency,
    )
