from scripts.common import load_yaml
from scripts.identify_procurement import identify_procurement

TAXONOMY = load_yaml("procurement_taxonomy.yml")


def identify(**kwargs):
    defaults = {
        "title": "",
        "field": "",
        "functional_area": "",
        "description": "",
        "responsibilities": "",
        "requirements": "",
        "taxonomy": TAXONOMY,
    }
    defaults.update(kwargs)
    return identify_procurement(**defaults)


def test_title_and_duty_phrases_are_included():
    sourcing = identify(title="Strategic sourcing and tender management")
    assert sourcing["procurementRelevant"] == "true"
    assert sourcing["procurementMatchBasis"] == "title"

    contracts = identify(title="Manage supplier contracts")
    assert contracts["procurementRelevant"] == "true"

    duties = identify(
        title="Assistant Manager",
        responsibilities="The officer will manage procurement for the department.",
    )
    assert duties["procurementRelevant"] == "true"
    assert duties["procurementMatchBasis"] == "duty_phrase"


def test_procurement_field_is_included_without_a_title_keyword():
    result = identify(title="Executive, Rail Licensing", field="Procurement")
    assert result["procurementRelevant"] == "true"
    assert result["procurementMatchBasis"] == "field"


def test_contract_employee_and_boilerplate_are_excluded():
    employee = identify(title="Contract employee", description="Two year employment contract.")
    assert employee["procurementRelevant"] == "false"
    assert employee["procurementMatchedTerms"].startswith("veto:")

    boilerplate = identify(
        title="Software Engineer",
        description=(
            "The Ministry of Finance is responsible for the Government Procurement (GP) "
            "policies, which govern how government agencies conduct their procurement."
        ),
    )
    assert boilerplate["procurementRelevant"] == "false"

    weak_pair = identify(
        title="Legal Counsel",
        description="Review the vendor tender pack and the supplier's response.",
    )
    assert weak_pair["procurementRelevant"] == "false"


def test_high_confidence_title_survives_a_contract_mention():
    result = identify(title="Assistant Director, Procurement (2 year contract)")
    assert result["procurementRelevant"] == "true"
