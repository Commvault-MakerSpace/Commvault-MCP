import pytest
from src.cv_mcp.api.paths import sanitize_endpoint_path


class TestSanitizeEndpointPath:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "v2/whoami",
            "Job/123/taskdetails",
            "v4/plan/summary/5",
            "Jobs?completedJobLookupTime=86400",
            "v2/plan?subType=Server&fq=plans.storage.copy.storagePoolType:in:1,4",
            "/Client",
            "Security/Dashboard",
        ],
    )
    def test_accepted_unchanged(self, endpoint):
        assert sanitize_endpoint_path(endpoint) == endpoint

    @pytest.mark.parametrize(
        "endpoint",
        [
            "",
            "Client/../etc",
            "..%2fetc",
            "%2e%2e/x",
            "Client/foo<bar",
            "a\\b",
            "Job/1|2",
        ],
    )
    def test_rejected_with_value_error(self, endpoint):
        with pytest.raises(ValueError):
            sanitize_endpoint_path(endpoint)

    def test_double_slashes_collapse(self):
        assert sanitize_endpoint_path("Client//5") == "Client/5"

    def test_non_string_input_raises(self):
        with pytest.raises(ValueError):
            sanitize_endpoint_path(None)
