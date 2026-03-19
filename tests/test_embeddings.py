from app.domain.embeddings import chunk_analysis


class TestChunkAnalysis:
    def test_chunks_components(self):
        data = {"components": [{"name": "API", "type": "gateway", "description": "Routes traffic"}]}
        chunks = chunk_analysis(data)
        assert len(chunks) == 1
        assert chunks[0]["section"] == "component"
        assert "API" in chunks[0]["text"]

    def test_chunks_component_with_technology(self):
        data = {"components": [{"name": "DB", "type": "database", "description": "Main", "technology": "PostgreSQL"}]}
        chunks = chunk_analysis(data)
        assert "PostgreSQL" in chunks[0]["text"]

    def test_chunks_connections(self):
        data = {"connections": [{"source": "A", "target": "B", "protocol": "HTTP", "description": "Calls"}]}
        chunks = chunk_analysis(data)
        assert chunks[0]["section"] == "connection"
        assert "A -> B" in chunks[0]["text"]

    def test_chunks_risks(self):
        data = {"risks": [{"severity": "high", "category": "security", "title": "No TLS", "description": "Unencrypted", "recommendation": "Add TLS"}]}
        chunks = chunk_analysis(data)
        assert chunks[0]["section"] == "risk"
        assert "No TLS" in chunks[0]["text"]
        assert "Add TLS" in chunks[0]["text"]

    def test_chunks_recommendations(self):
        data = {"recommendations": ["Add caching", "Use CDN"]}
        chunks = chunk_analysis(data)
        assert len(chunks) == 2
        assert all(c["section"] == "recommendation" for c in chunks)

    def test_chunks_scores(self):
        data = {"scores": {"scalability": 7, "security": 8, "reliability": 6, "maintainability": 7, "overall": 7}}
        chunks = chunk_analysis(data)
        assert chunks[0]["section"] == "scores"
        assert "7/10" in chunks[0]["text"]

    def test_chunks_metadata(self):
        data = {"confidence": 0.85, "providers_used": ["openai", "gemini"]}
        chunks = chunk_analysis(data)
        assert chunks[0]["section"] == "metadata"
        assert "85%" in chunks[0]["text"]
        assert "openai" in chunks[0]["text"]

    def test_chunks_empty_data(self):
        chunks = chunk_analysis({})
        assert chunks == []

    def test_chunks_full_analysis(self):
        data = {
            "components": [{"name": "API", "type": "gateway", "description": "Entry"}],
            "connections": [{"source": "API", "target": "DB", "protocol": "TCP"}],
            "risks": [{"severity": "medium", "category": "reliability", "title": "SPOF", "description": "No failover", "recommendation": "Add replica"}],
            "recommendations": ["Add monitoring"],
            "scores": {"scalability": 7, "security": 8, "reliability": 6, "maintainability": 7, "overall": 7},
            "confidence": 0.9,
            "providers_used": ["openai"],
        }
        chunks = chunk_analysis(data)
        sections = [c["section"] for c in chunks]
        assert "component" in sections
        assert "connection" in sections
        assert "risk" in sections
        assert "recommendation" in sections
        assert "scores" in sections
        assert "metadata" in sections
