import modal

app = modal.App("policyengine-uk-demo")

image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "policyengine-uk",  # Latest version (requires Python 3.13+)
    "fastapi[standard]",
)


def do_calculation(reform: dict = None, incomes: list = None, num_children: int = 2):
    """Core calculation logic using policyengine-uk Python package."""
    from policyengine_uk import Simulation

    if incomes is None:
        incomes = [15000, 20000, 25000, 30000, 35000, 40000, 50000, 60000, 70000, 80000, 100000]

    if reform is None:
        reform = {
            "gov.hmrc.child_benefit.amount.eldest": {"2024-01-01.2100-12-31": 52.10},
            "gov.hmrc.child_benefit.amount.additional": {"2024-01-01.2100-12-31": 34.50},
            "gov.hmrc.income_tax.charges.CB_HITC.phase_out_start": {"2024-01-01.2100-12-31": 10_000_000},
        }

    year = 2024
    results = []

    for income in incomes:
        members = ["parent"] + [f"child{i+1}" for i in range(num_children)]

        situation = {
            "people": {
                "parent": {
                    "age": {year: 35},
                    "employment_income": {year: income},
                },
                **{f"child{i+1}": {"age": {year: max(2, 8 - i*3)}} for i in range(num_children)}
            },
            "benunits": {"benunit": {"members": members}},
            "households": {"household": {"members": members, "region": {year: "LONDON"}}},
        }

        # Baseline
        baseline = Simulation(situation=situation)
        baseline_net = float(baseline.calculate("household_net_income", year).sum())
        baseline_cb = float(baseline.calculate("child_benefit", year).sum())

        # Reform
        reformed = Simulation(situation=situation, reform=reform)
        reformed_net = float(reformed.calculate("household_net_income", year).sum())
        reformed_cb = float(reformed.calculate("child_benefit", year).sum())

        change = reformed_net - baseline_net
        pct_change = (change / baseline_net * 100) if baseline_net > 0 else 0

        results.append({
            "income": income,
            "baseline_net": round(baseline_net, 0),
            "reformed_net": round(reformed_net, 0),
            "change": round(change, 0),
            "pct_change": round(pct_change, 1),
            "baseline_cb": round(baseline_cb, 2),
            "reformed_cb": round(reformed_cb, 2),
        })

    return {"results": results, "num_children": num_children, "reform": reform}


@app.function(image=image, timeout=300, memory=4096)
def run_calculation(reform: dict = None, incomes: list = None, num_children: int = 2):
    """Modal function for running the calculation."""
    return do_calculation(reform, incomes, num_children)


@app.function(image=image, timeout=300, memory=4096)
@modal.fastapi_endpoint(method="POST")
def calculate(reform: dict = None, incomes: list = None, num_children: int = 2):
    """Web endpoint for calculations."""
    return do_calculation(reform, incomes, num_children)


@app.function(image=image, timeout=60)
@modal.fastapi_endpoint(method="GET")
def health():
    """Health check."""
    return {"status": "ok", "service": "policyengine-uk-demo", "package": "policyengine-uk"}


@app.local_entrypoint()
def test():
    """Test the calculation via Modal."""
    print("Testing with a single income point...")
    result = run_calculation.remote(num_children=2, incomes=[35000])
    print(result)
