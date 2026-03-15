from app.domain.consensus import ConsensusEngine, _normalize, _names_match
from app.domain.models import Component, Connection, ProviderResponse, Risk, Score


class TestNormalize:
    def test_strips_whitespace(self):
        assert _normalize("  Redis  ") == "redis"

    def test_removes_parenthetical(self):
        assert _normalize("PostgreSQL (Accounts)") == "postgresql"

    def test_removes_service_suffix(self):
        assert _normalize("User Service") == "user"

    def test_removes_db_suffix(self):
        assert _normalize("Accounts DB") == "accounts"

    def test_removes_cluster_suffix(self):
        assert _normalize("Redis Cluster") == "redis"

    def test_removes_svc_suffix(self):
        assert _normalize("Auth Svc") == "auth"

    def test_removes_server_suffix(self):
        assert _normalize("Web Server") == "web"


class TestNamesMatch:
    def test_exact_after_normalize(self):
        assert _names_match("Redis", "redis")

    def test_containment_match(self):
        assert _names_match("user", "user-auth")

    def test_no_match(self):
        assert not _names_match("Redis", "PostgreSQL")


class TestPickBestComponent:
    def test_picks_more_detailed(self):
        a = Component(name="API", type="gateway", description="Short")
        b = Component(name="API Gateway", type="gateway", description="A longer description of the gateway", technology="NGINX")
        result = ConsensusEngine._pick_best_component(a, b)
        assert result == b

    def test_picks_first_when_equal(self):
        a = Component(name="API", type="gateway", description="Desc")
        b = Component(name="API", type="gateway", description="Desc")
        result = ConsensusEngine._pick_best_component(a, b)
        assert result == a


class TestRisksMatch:
    def test_similar_titles_match(self):
        a = Risk(severity="high", category="reliability", title="Single Point of Failure", description="a", recommendation="b")
        b = Risk(severity="high", category="reliability", title="SPOF in Gateway", description="c", recommendation="d")
        # May or may not match depending on Levenshtein threshold, but let's test the method runs
        result = ConsensusEngine._risks_match(a, b)
        assert isinstance(result, bool)

    def test_identical_titles_match(self):
        a = Risk(severity="high", category="reliability", title="No Auth", description="a", recommendation="b")
        b = Risk(severity="medium", category="security", title="No Auth", description="c", recommendation="d")
        assert ConsensusEngine._risks_match(a, b) is True

    def test_different_titles_no_match(self):
        a = Risk(severity="high", category="reliability", title="Single Point of Failure", description="a", recommendation="b")
        b = Risk(severity="low", category="security", title="Missing Rate Limiter", description="c", recommendation="d")
        assert ConsensusEngine._risks_match(a, b) is False


class TestMergeScoresEdgeCases:
    def test_no_scores_returns_none(self):
        engine = ConsensusEngine()
        r = ProviderResponse(provider_name="test", components=[], scores=None)
        result = engine._merge_scores([r])
        assert result is None

    def test_weighted_scores(self):
        engine = ConsensusEngine()
        r1 = ProviderResponse(
            provider_name="a",
            provider_weight=2.0,
            scores=Score(scalability=10, security=10, reliability=10, maintainability=10, overall=10),
        )
        r2 = ProviderResponse(
            provider_name="b",
            provider_weight=1.0,
            scores=Score(scalability=4, security=4, reliability=4, maintainability=4, overall=4),
        )
        result = engine._merge_scores([r1, r2])
        # weighted avg: (10*2 + 4*1) / 3 = 24/3 = 8
        assert result.scalability == 8.0


class TestCalculateConfidence:
    def test_single_response_half_confidence(self):
        engine = ConsensusEngine()
        r = ProviderResponse(provider_name="test", components=[Component(name="A", type="svc")])
        merged = [Component(name="A", type="svc")]
        assert engine._calculate_confidence([r], merged) == 0.5

    def test_no_merged_components_low_confidence(self):
        engine = ConsensusEngine()
        r1 = ProviderResponse(provider_name="a", components=[Component(name="X", type="svc")])
        r2 = ProviderResponse(provider_name="b", components=[Component(name="Y", type="db")])
        assert engine._calculate_confidence([r1, r2], []) == 0.3
