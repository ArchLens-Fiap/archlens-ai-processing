from collections import defaultdict

import structlog
from Levenshtein import ratio as levenshtein_ratio

from app.domain.models import (
    Component,
    Connection,
    ConsensusResult,
    ProviderResponse,
    Risk,
    Score,
)

logger = structlog.get_logger()

FUZZY_MATCH_THRESHOLD = 0.65
MIN_CONFIDENCE_THRESHOLD = 0.3


def _normalize(name: str) -> str:
    """Normalize component/risk names for better matching."""
    n = name.lower().strip()
    # Remove parenthetical details: "PostgreSQL (Accounts)" -> "postgresql"
    if "(" in n:
        n = n[:n.index("(")].strip()
    # Remove common suffixes
    for suffix in (" service", " svc", " server", " db", " cluster"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def _names_match(a: str, b: str) -> bool:
    """Check if two names refer to the same entity."""
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return True
    # One contains the other
    if na in nb or nb in na:
        return True
    return levenshtein_ratio(na, nb) > FUZZY_MATCH_THRESHOLD


class ConsensusEngine:

    def build_consensus(self, responses: list[ProviderResponse]) -> ConsensusResult:
        if not responses:
            return ConsensusResult(confidence=0.0)

        if len(responses) == 1:
            r = responses[0]
            return ConsensusResult(
                components=r.components,
                connections=r.connections,
                risks=r.risks,
                recommendations=r.recommendations,
                scores=r.scores,
                providers_used=[r.provider_name],
                confidence=0.5,
            )

        components = self._merge_components(responses)
        connections = self._merge_connections(responses)
        risks = self._merge_risks(responses)
        recommendations = self._merge_recommendations(responses)
        scores = self._merge_scores(responses)
        confidence = self._calculate_confidence(responses, components)

        return ConsensusResult(
            components=components,
            connections=connections,
            risks=risks,
            recommendations=recommendations,
            scores=scores,
            providers_used=[r.provider_name for r in responses],
            confidence=round(confidence, 2),
        )

    def _merge_components(self, responses: list[ProviderResponse]) -> list[Component]:
        all_components: list[tuple[Component, int]] = []

        for resp in responses:
            for comp in resp.components:
                matched = False
                for i, (existing, count) in enumerate(all_components):
                    if _names_match(comp.name, existing.name):
                        all_components[i] = (
                            self._pick_best_component(existing, comp),
                            count + 1,
                        )
                        matched = True
                        break
                if not matched:
                    all_components.append((comp, 1))

        total = len(responses)
        return [
            comp for comp, count in all_components
            if count / total >= MIN_CONFIDENCE_THRESHOLD
        ]

    def _merge_connections(self, responses: list[ProviderResponse]) -> list[Connection]:
        seen: list[tuple[Connection, str]] = []

        for resp in responses:
            for conn in resp.connections:
                src = _normalize(conn.source)
                tgt = _normalize(conn.target)
                key = f"{src}|{tgt}"
                is_dup = False
                for _, existing_key in seen:
                    if existing_key == key:
                        is_dup = True
                        break
                    # Check reverse too
                    parts = existing_key.split("|")
                    if len(parts) == 2:
                        if (_names_match(src, parts[0]) and _names_match(tgt, parts[1])):
                            is_dup = True
                            break
                if not is_dup:
                    seen.append((conn, key))

        return [conn for conn, _ in seen]

    def _merge_risks(self, responses: list[ProviderResponse]) -> list[Risk]:
        all_risks: list[tuple[Risk, int]] = []

        for resp in responses:
            for risk in resp.risks:
                matched = False
                for i, (existing, count) in enumerate(all_risks):
                    if self._risks_match(risk, existing):
                        if len(risk.description) > len(existing.description):
                            all_risks[i] = (risk, count + 1)
                        else:
                            all_risks[i] = (existing, count + 1)
                        matched = True
                        break
                if not matched:
                    all_risks.append((risk, 1))

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_risks.sort(key=lambda x: severity_order.get(x[0].severity, 4))

        return [risk for risk, _ in all_risks]

    def _merge_recommendations(self, responses: list[ProviderResponse]) -> list[str]:
        seen: list[str] = []

        for resp in responses:
            for rec in resp.recommendations:
                is_duplicate = any(
                    levenshtein_ratio(rec.lower(), existing.lower()) > FUZZY_MATCH_THRESHOLD
                    for existing in seen
                )
                if not is_duplicate:
                    seen.append(rec)

        return seen

    def _merge_scores(self, responses: list[ProviderResponse]) -> Score | None:
        valid = [(r.scores, r.provider_weight) for r in responses if r.scores is not None]
        if not valid:
            return None

        total_weight = sum(w for _, w in valid)
        if total_weight == 0:
            total_weight = len(valid)

        return Score(
            scalability=round(sum(s.scalability * w for s, w in valid) / total_weight, 1),
            security=round(sum(s.security * w for s, w in valid) / total_weight, 1),
            reliability=round(sum(s.reliability * w for s, w in valid) / total_weight, 1),
            maintainability=round(sum(s.maintainability * w for s, w in valid) / total_weight, 1),
            overall=round(sum(s.overall * w for s, w in valid) / total_weight, 1),
        )

    def _calculate_confidence(
        self, responses: list[ProviderResponse], merged_components: list[Component]
    ) -> float:
        if len(responses) < 2:
            return 0.5

        component_counts: dict[str, int] = defaultdict(int)
        for resp in responses:
            for comp in resp.components:
                for merged in merged_components:
                    if _names_match(comp.name, merged.name):
                        component_counts[merged.name] += 1
                        break

        if not component_counts:
            return 0.3

        total = len(responses)
        agreement_scores = [min(count / total, 1.0) for count in component_counts.values()]
        return min(sum(agreement_scores) / len(agreement_scores), 1.0)

    @staticmethod
    def _pick_best_component(a: Component, b: Component) -> Component:
        # Prefer the one with more detail (longer description + name with parenthetical info)
        a_score = len(a.description) + len(a.name) + len(a.technology)
        b_score = len(b.description) + len(b.name) + len(b.technology)
        return a if a_score >= b_score else b

    @staticmethod
    def _risks_match(a: Risk, b: Risk) -> bool:
        # Match risks across categories too — title similarity is more important
        title_sim = levenshtein_ratio(a.title.lower(), b.title.lower())
        if title_sim > FUZZY_MATCH_THRESHOLD:
            return True
        # Also check if normalized titles match
        if _names_match(a.title, b.title):
            return True
        return False
