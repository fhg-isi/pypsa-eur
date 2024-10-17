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
    options["endogenous_steel"] = True

    if options["endogenous_steel"]:
        logger.info("Adding endogenous primary steel demand in tonnes.")

        sector = "DRI + Electric arc"

        no_relocation = not options.get("relocation_steel", False)
        no_flexibility = not options.get("flexibility_steel", False)

        s = " not" if no_relocation else " "
        logger.info(f"Steel industry relocation{s} activated.")

        s = " not" if no_flexibility else " "
        logger.info(f"Steel industry flexibility{s} activated.")

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

        n.add(
            "Load",
            "EU steel",
            bus="EU steel",
            carrier="steel",
            p_set=industrial_production[sector].sum() / nhours,
        )

        if not no_flexibility:
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

        electricity_input = costs.at[
            "direct iron reduction furnace", "electricity-input"
        ]

        hydrogen_input = costs.at["direct iron reduction furnace", "hydrogen-input"]

        # so that for each region supply matches consumption
        p_nom = (
            industrial_production[sector]
            * costs.at["electric arc furnace", "hbi-input"]
            * electricity_input
            / nhours
        )

        marginal_cost = (
            costs.at["iron ore DRI-ready", "commodity"]
            * costs.at["direct iron reduction furnace", "ore-input"]
            / electricity_input
        )

        n.madd(
            "Link",
            nodes,
            suffix=" DRI",
            carrier="DRI",
            capital_cost=costs.at["direct iron reduction furnace", "fixed"]
            / electricity_input,
            marginal_cost=marginal_cost,
            p_nom_max=p_nom if no_relocation else np.inf,
            p_nom_extendable=True,
            p_min_pu=1 if no_flexibility else 0,
            bus0=nodes,
            bus1="EU HBI",
            bus2=nodes + " H2",
            efficiency=1 / electricity_input,
            efficiency2=-hydrogen_input / electricity_input,
        )

        electricity_input = costs.at["electric arc furnace", "electricity-input"]

        p_nom = industrial_production[sector] * electricity_input / nhours

        n.madd(
            "Link",
            nodes,
            suffix=" EAF",
            carrier="EAF",
            capital_cost=costs.at["electric arc furnace", "fixed"] / electricity_input,
            p_nom_max=p_nom if no_relocation else np.inf,
            p_nom_extendable=True,
            p_min_pu=1 if no_flexibility else 0,
            bus0=nodes,
            bus1="EU steel",
            bus2="EU HBI",
            efficiency=1 / electricity_input,
            efficiency2=-costs.at["electric arc furnace", "hbi-input"]
            / electricity_input,
        )

    return n
