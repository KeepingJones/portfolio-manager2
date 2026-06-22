from typing import Optional


def project_growth(
    current_value: float,
    years: int = 20,
) -> dict:
    """
    Returns yearly portfolio value under 4 CAGR scenarios.
    """
    scenarios = {
        "Conservative (3%)": 0.03,
        "Moderate (5%)": 0.05,
        "Optimistic (7%)": 0.07,
        "Aggressive (10%)": 0.10,
    }
    year_labels = list(range(1, years + 1))
    return {
        "current_value": round(current_value, 2),
        "years": year_labels,
        "scenarios": {
            label: [round(current_value * (1 + rate) ** y, 2) for y in year_labels]
            for label, rate in scenarios.items()
        },
    }


def project_income(
    annual_income: float,
    years: int = 10,
) -> dict:
    """
    Returns projected annual dividend income under 3 growth scenarios.
    """
    scenarios = {
        "Flat": [round(annual_income, 2)] * years,
        "3% Growth": [round(annual_income * (1.03 ** y), 2) for y in range(1, years + 1)],
        "5% Growth": [round(annual_income * (1.05 ** y), 2) for y in range(1, years + 1)],
    }
    return {
        "current_annual_income": round(annual_income, 2),
        "years": list(range(1, years + 1)),
        "scenarios": scenarios,
    }


def project_total_return(
    current_value: float,
    annual_income: float,
    years: int = 20,
    growth_rate: float = 0.05,
    income_growth_rate: float = 0.03,
) -> dict:
    """
    Total return: capital growth + dividends.
    Two variants: reinvested vs taken as cash.
    """
    year_labels = list(range(1, years + 1))

    # Cash: value grows at growth_rate, income taken out each year
    cash_values = []
    cash_cumulative_income = []
    val = current_value
    inc = annual_income
    cum_inc = 0.0
    for _ in year_labels:
        val = val * (1 + growth_rate)
        inc = inc * (1 + income_growth_rate)
        cum_inc += inc
        cash_values.append(round(val, 2))
        cash_cumulative_income.append(round(cum_inc, 2))

    # Reinvested: dividends added back to portfolio, then compound
    reinvest_values = []
    val = current_value
    inc = annual_income
    for _ in year_labels:
        val = val * (1 + growth_rate) + inc
        inc = inc * (1 + income_growth_rate)
        reinvest_values.append(round(val, 2))

    return {
        "years": year_labels,
        "cash_portfolio_value": cash_values,
        "cash_cumulative_income": cash_cumulative_income,
        "reinvested_portfolio_value": reinvest_values,
    }
