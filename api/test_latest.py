import modal

app = modal.App("policyengine-uk-test")

image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "policyengine-uk",  # Latest version
    "fastapi[standard]",
)


@app.function(image=image, timeout=300, memory=4096)
def test_issues():
    """Test if issues are fixed in 2.59.0."""
    from policyengine_uk import Simulation

    results = {}

    # Test 1: Does API-style period format work?
    try:
        reform_api_style = {
            "gov.hmrc.child_benefit.amount.eldest": {"2024-01-01.2100-12-31": 52.10},
        }
        situation = {
            "people": {"parent": {"age": {2024: 35}, "employment_income": {2024: 35000}}, "child": {"age": {2024: 5}}},
            "benunits": {"benunit": {"members": ["parent", "child"]}},
            "households": {"household": {"members": ["parent", "child"], "region": {2024: "LONDON"}}},
        }
        sim = Simulation(situation=situation, reform=reform_api_style)
        results["api_period_format"] = "WORKS"
    except Exception as e:
        results["api_period_format"] = f"FAILS: {type(e).__name__}: {str(e)[:100]}"

    # Test 2: Does it work WITHOUT sim.dataset = None?
    try:
        reform = {
            "gov.hmrc.child_benefit.amount.eldest": {"year:2024:10": 52.10},
        }
        sim = Simulation(situation=situation, reform=reform)
        # Don't set sim.dataset = None
        cb = sim.calculate("child_benefit", 2024)
        results["without_dataset_none"] = f"WORKS: child_benefit = {float(cb.sum()):.2f}"
    except Exception as e:
        results["without_dataset_none"] = f"FAILS: {type(e).__name__}: {str(e)[:100]}"

    # Test 3: Does household_net_income work without workaround?
    try:
        sim = Simulation(situation=situation)
        net = sim.calculate("household_net_income", 2024)
        results["household_net_income"] = f"WORKS: {float(net.sum()):.2f}"
    except Exception as e:
        results["household_net_income"] = f"FAILS: {type(e).__name__}: {str(e)[:100]}"

    return results


@app.local_entrypoint()
def main():
    results = test_issues.remote()
    print("\n=== Testing policyengine-uk 2.59.0 ===\n")
    for test, result in results.items():
        status = "✅" if "WORKS" in result else "❌"
        print(f"{status} {test}: {result}")
