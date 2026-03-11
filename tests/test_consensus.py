from app.domain.consensus import ConsensusEngine
from app.domain.models import Component, Connection, ProviderResponse, Risk, Score


class TestConsensusEngine:
    def setup_method(self):
        self.engine = ConsensusEngine()

    def test_empty_responses_returns_zero_confidence(self):
        result = self.engine.build_consensus([])
        assert result.confidence == 0.0
        assert result.components == []

    def test_single_response_returns_half_confidence(self, sample_provider_response):
        result = self.engine.build_consensus([sample_provider_response])
        assert result.confidence == 0.5
        assert len(result.components) == 3
        assert result.providers_used == ["openai"]

    def test_two_providers_merge_components(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        assert result.confidence > 0.5
        assert len(result.providers_used) == 2

        names = [c.name for c in result.components]
        assert "API Gateway" in names
        assert "PostgreSQL" in names

    def test_fuzzy_match_merges_similar_names(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        names = [c.name.lower() for c in result.components]
        user_variants = [n for n in names if "user" in n]
        assert len(user_variants) == 1

    def test_risks_sorted_by_severity(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        if len(result.risks) >= 2:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(result.risks) - 1):
                current = severity_order.get(result.risks[i].severity, 4)
                next_val = severity_order.get(result.risks[i + 1].severity, 4)
                assert current <= next_val

    def test_recommendations_deduplication(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        lower_recs = [r.lower() for r in result.recommendations]
        circuit_breaker_count = sum(1 for r in lower_recs if "circuit breaker" in r)
        assert circuit_breaker_count == 1

    def test_scores_averaged(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        assert result.scores is not None
        assert result.scores.scalability == 7.5
        assert result.scores.security == 7.5
        assert result.scores.reliability == 6.5
        assert result.scores.maintainability == 7.5

    def test_connections_deduplication(self, two_provider_responses):
        result = self.engine.build_consensus(two_provider_responses)

        keys = set()
        for conn in result.connections:
            key = f"{conn.source.lower()}|{conn.target.lower()}"
            assert key not in keys
            keys.add(key)


class TestComponentMatching:
    def test_exact_match(self):
        assert ConsensusEngine._components_match(
            Component(name="Redis", type="cache"),
            Component(name="Redis", type="cache"),
        )

    def test_case_insensitive_match(self):
        assert ConsensusEngine._components_match(
            Component(name="redis", type="cache"),
            Component(name="Redis", type="cache"),
        )

    def test_fuzzy_match(self):
        assert ConsensusEngine._components_match(
            Component(name="User Service", type="microservice"),
            Component(name="Users Service", type="microservice"),
        )

    def test_no_match(self):
        assert not ConsensusEngine._components_match(
            Component(name="Redis", type="cache"),
            Component(name="PostgreSQL", type="database"),
        )
