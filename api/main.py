import modal

app = modal.App("policyengine-uk-demo")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "policyengine-uk",
    "fastapi[standard]",
    "requests",
)

@app.function(image=image, timeout=300)
@modal.web_endpoint(method="POST")
def calculate(reform: dict = None, incomes: list = None, num_children: int = 2):
    """Calculate reform impacts for households across income distribution."""
    import requests

    API_URL = "https://api.policyengine.org"

    if incomes is None:
        incomes = [15000, 20000, 25000, 30000, 35000, 40000, 50000, 60000, 70000, 80000, 100000]

    if reform is None:
        # Default: Double Child Benefit + abolish HICBC
        reform = {
            "gov.hmrc.child_benefit.amount.eldest": {"2024-01-01.2100-12-31": 52.10},
            "gov.hmrc.child_benefit.amount.additional": {"2024-01-01.2100-12-31": 34.50},
            "gov.hmrc.income_tax.charges.CB_HITC.phase_out_start": {"2024-01-01.2100-12-31": 10_000_000},
        }

    year = 2024
    results = []

    for income in incomes:
        # Build household
        people = {
            "parent": {
                "age": {str(year): 35},
                "employment_income": {str(year): income},
                "income_tax": {str(year): None},
            }
        }
        members = ["parent"]

        for i in range(num_children):
            child_id = f"child{i+1}"
            people[child_id] = {"age": {str(year): max(2, 8 - i*3)}}
            members.append(child_id)

        household = {
            "people": people,
            "benunits": {
                "benunit": {
                    "members": members,
                    "child_benefit": {str(year): None},
                }
            },
            "households": {
                "household": {
                    "members": members,
                    "region": {str(year): "LONDON"},
                    "household_net_income": {str(year): None},
                }
            },
        }

        # Calculate baseline
        baseline_resp = requests.post(
            f"{API_URL}/uk/calculate",
            json={"household": household},
            timeout=60
        )
        baseline = baseline_resp.json().get("result", {})

        # Calculate reform
        reform_resp = requests.post(
            f"{API_URL}/uk/calculate",
            json={"household": household, "policy": reform},
            timeout=60
        )
        reformed = reform_resp.json().get("result", {})

        baseline_net = baseline.get("households", {}).get("household", {}).get("household_net_income", {}).get(str(year), 0)
        reformed_net = reformed.get("households", {}).get("household", {}).get("household_net_income", {}).get(str(year), 0)
        baseline_cb = baseline.get("benunits", {}).get("benunit", {}).get("child_benefit", {}).get(str(year), 0)
        reformed_cb = reformed.get("benunits", {}).get("benunit", {}).get("child_benefit", {}).get(str(year), 0)

        change = reformed_net - baseline_net
        pct_change = (change / baseline_net * 100) if baseline_net > 0 else 0

        results.append({
            "income": income,
            "baseline_net": baseline_net,
            "reformed_net": reformed_net,
            "change": round(change, 0),
            "pct_change": round(pct_change, 1),
            "baseline_cb": baseline_cb,
            "reformed_cb": reformed_cb,
        })

    return {"results": results, "num_children": num_children, "reform": reform}


@app.function(image=image, timeout=60)
@modal.web_endpoint(method="GET")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "policyengine-uk-demo"}
