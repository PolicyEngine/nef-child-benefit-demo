import modal

app = modal.App("policyengine-uk-demo")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "policyengine-uk==2.45.4",
    "fastapi[standard]",
)


def do_calculation(reform: dict = None, incomes: list = None, num_children: int = 2):
    """Core calculation logic using policyengine-uk Python package."""
    from policyengine_uk import Simulation

    if incomes is None:
        incomes = [15000, 20000, 25000, 30000, 35000, 40000, 50000, 60000, 70000, 80000, 100000]

    if reform is None:
        reform = {
            "gov.hmrc.child_benefit.amount.eldest": {"year:2024:10": 52.10},
            "gov.hmrc.child_benefit.amount.additional": {"year:2024:10": 34.50},
            "gov.hmrc.income_tax.charges.CB_HITC.phase_out_start": {"year:2024:10": 10_000_000},
        }

    year = 2024
    results = []

    for income in incomes:
        # Build situation dict
        members = ["parent"] + [f"child{i+1}" for i in range(num_children)]

        situation = {
            "people": {
                "parent": {
                    "age": {year: 35},
                    "employment_income": {year: income},
                },
                **{
                    f"child{i+1}": {"age": {year: max(2, 8 - i*3)}}
                    for i in range(num_children)
                }
            },
            "benunits": {
                "benunit": {"members": members}
            },
            "households": {
                "household": {
                    "members": members,
                    "region": {year: "LONDON"},
                }
            },
        }

        # Baseline calculation
        baseline_sim = Simulation(situation=situation)
        baseline_sim.dataset = None

        baseline_income_tax = float(baseline_sim.calculate("income_tax", year).sum())
        baseline_ni = float(baseline_sim.calculate("national_insurance", year).sum())
        baseline_gross = float(baseline_sim.calculate("total_income", year).sum())

        # For child benefit, directly get the amount paid after CB_HITC
        baseline_child_benefit_entitlement = float(baseline_sim.calculate("child_benefit_entitlement", year).sum())
        baseline_cb_hitc = float(baseline_sim.calculate("CB_HITC", year).sum())

        baseline_cb = baseline_child_benefit_entitlement - baseline_cb_hitc
        baseline_net = baseline_gross - baseline_income_tax - baseline_ni + baseline_cb

        # Reform calculation
        reformed_sim = Simulation(situation=situation, reform=reform)
        reformed_sim.dataset = None

        reformed_income_tax = float(reformed_sim.calculate("income_tax", year).sum())
        reformed_ni = float(reformed_sim.calculate("national_insurance", year).sum())
        reformed_gross = float(reformed_sim.calculate("total_income", year).sum())
        reformed_child_benefit_entitlement = float(reformed_sim.calculate("child_benefit_entitlement", year).sum())
        reformed_cb_hitc = float(reformed_sim.calculate("CB_HITC", year).sum())

        reformed_cb = reformed_child_benefit_entitlement - reformed_cb_hitc
        reformed_net = reformed_gross - reformed_income_tax - reformed_ni + reformed_cb

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
