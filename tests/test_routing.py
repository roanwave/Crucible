"""Tests for Router implementations."""

import pytest

from crucible.config import CouncilRole, EngineConfig, RoutingMode
from crucible.routing import (
    CostAwareRouter,
    DiversityRouter,
    PoolRouter,
    RoleMappedRouter,
    RoleSpecializedRouter,
    TieredRouter,
)
from crucible.routing.base import count_vendor_in_selections, extract_vendor, safe_fallback


class TestBaseUtilities:
    """Tests for base routing utilities."""

    def test_extract_vendor_standard(self):
        """Test vendor extraction from standard model IDs."""
        assert extract_vendor("anthropic/claude-opus-4") == "anthropic"
        assert extract_vendor("openai/gpt-4o") == "openai"
        assert extract_vendor("google/gemini-2.5-pro") == "google"
        assert extract_vendor("openrouter/auto") == "openrouter"

    def test_extract_vendor_no_slash(self):
        """Test vendor extraction when no slash present."""
        assert extract_vendor("some-model") == "unknown"

    def test_count_vendor_in_selections(self):
        """Test counting vendor occurrences."""
        selections = [
            "anthropic/claude-opus-4",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
        ]
        assert count_vendor_in_selections("anthropic", selections) == 2
        assert count_vendor_in_selections("openai", selections) == 1
        assert count_vendor_in_selections("google", selections) == 0

    def test_safe_fallback_valid(self):
        """Test safe_fallback with valid input."""
        assert safe_fallback("anthropic/claude-opus-4") == "anthropic/claude-opus-4"

    def test_safe_fallback_empty(self):
        """Test safe_fallback with empty/invalid input."""
        assert safe_fallback("") == "openrouter/auto"
        assert safe_fallback(None) == "openrouter/auto"
        assert safe_fallback("   ") == "openrouter/auto"


class TestPoolRouter:
    """Tests for PoolRouter."""

    def test_basic_selection(self):
        """Test basic model selection from pool."""
        pool = ["anthropic/claude-opus-4", "openai/gpt-4o"]
        router = PoolRouter(model_pool=pool)

        model = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model in pool

    def test_empty_pool_raises(self):
        """Test that empty pool raises ValueError."""
        with pytest.raises(ValueError, match="model_pool cannot be empty"):
            PoolRouter(model_pool=[])

    def test_ignores_role_and_diversity(self):
        """Test that PoolRouter ignores role and existing selections."""
        pool = ["anthropic/claude-opus-4"]
        router = PoolRouter(model_pool=pool)

        # Should return same model regardless of role or existing selections
        for role in CouncilRole:
            model = router.select_model(
                role=role,
                loop=0,
                seat_index=0,
                existing_selections=["anthropic/claude-opus-4"] * 5,
            )
            assert model == "anthropic/claude-opus-4"


class TestDiversityRouter:
    """Tests for DiversityRouter."""

    def test_basic_selection(self):
        """Test basic model selection with diversity."""
        pool = [
            "anthropic/claude-opus-4",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
        ]
        router = DiversityRouter(model_pool=pool, max_per_vendor=2)

        model = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model in pool

    def test_diversity_constraint(self):
        """Test that vendor diversity is enforced."""
        pool = [
            "anthropic/claude-opus-4",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
        ]
        router = DiversityRouter(model_pool=pool, max_per_vendor=1)

        # First selection with no prior
        model1 = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )

        # Second selection with anthropic already used
        model2 = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=1,
            existing_selections=["anthropic/claude-opus-4"],
        )

        # If we used anthropic first, second must be openai
        if model1.startswith("anthropic/"):
            assert model2 == "openai/gpt-4o"

    def test_fallback_when_exhausted(self):
        """Test fallback when all vendors exhausted."""
        pool = ["anthropic/claude-opus-4"]
        router = DiversityRouter(model_pool=pool, max_per_vendor=1)

        # Exhaust anthropic
        model = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=1,
            existing_selections=["anthropic/claude-opus-4"],
        )
        assert model == "openrouter/auto"


class TestRoleMappedRouter:
    """Tests for RoleMappedRouter."""

    def test_role_mapping(self):
        """Test that roles map to correct models."""
        role_models = {
            CouncilRole.RED_TEAM: ["anthropic/claude-haiku-4"],
            CouncilRole.SYNTHESIZER: ["anthropic/claude-opus-4"],
        }
        router = RoleMappedRouter(role_models=role_models)

        assert router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-haiku-4"

        assert router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-opus-4"

    def test_default_fallback(self):
        """Test fallback for unmapped roles."""
        role_models = {
            CouncilRole.RED_TEAM: ["anthropic/claude-haiku-4"],
        }
        router = RoleMappedRouter(role_models=role_models, default="openrouter/auto")

        # DOMAIN_EXPERT not in role_models, should use default
        model = router.select_model(
            role=CouncilRole.DOMAIN_EXPERT,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model == "openrouter/auto"


class TestTieredRouter:
    """Tests for TieredRouter."""

    def test_premium_roles(self):
        """Test that premium roles get premium model."""
        router = TieredRouter(
            premium_model="anthropic/claude-opus-4",
            budget_model="anthropic/claude-sonnet-4",
        )

        assert router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-opus-4"

        assert router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-opus-4"

    def test_budget_roles(self):
        """Test that other roles get budget model."""
        router = TieredRouter(
            premium_model="anthropic/claude-opus-4",
            budget_model="anthropic/claude-sonnet-4",
        )

        assert router.select_model(
            role=CouncilRole.DOMAIN_EXPERT,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-sonnet-4"

        assert router.select_model(
            role=CouncilRole.PRAGMATIST,
            loop=0,
            seat_index=0,
            existing_selections=[],
        ) == "anthropic/claude-sonnet-4"


class TestRoleSpecializedRouter:
    """Tests for RoleSpecializedRouter."""

    def test_basic_selection(self):
        """Verify RoleSpecializedRouter returns models from configured pools."""
        pools = {
            CouncilRole.RED_TEAM: [
                "anthropic/claude-haiku-4",
                "mistralai/mistral-large",
            ],
            CouncilRole.SYNTHESIZER: [
                "anthropic/claude-opus-4",
            ],
        }

        router = RoleSpecializedRouter(role_pools=pools)

        # RED_TEAM should return a model from its pool
        model = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model in pools[CouncilRole.RED_TEAM]

        # SYNTHESIZER should return its model
        model = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model == "anthropic/claude-opus-4"

    def test_diversity_constraint(self):
        """Verify vendor diversity is enforced."""
        pools = {
            CouncilRole.RED_TEAM: [
                "anthropic/claude-haiku-4",
                "anthropic/claude-sonnet-4",
                "mistralai/mistral-large",
            ],
        }

        router = RoleSpecializedRouter(
            role_pools=pools,
            max_per_vendor=1,  # Max 1 per vendor
        )

        # First selection (no existing)
        model1 = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )

        # Second selection (with anthropic already selected)
        # Should avoid anthropic, pick mistral
        model2 = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=1,
            existing_selections=[model1],
        )

        # If model1 is anthropic, model2 must be mistral
        if model1.startswith("anthropic/"):
            assert model2 == "mistralai/mistral-large"

    def test_fallback_to_auto(self):
        """Verify fallback to openrouter/auto when pool exhausted."""
        pools = {
            CouncilRole.RED_TEAM: [
                "anthropic/claude-haiku-4",
            ],
        }

        router = RoleSpecializedRouter(
            role_pools=pools,
            max_per_vendor=1,
        )

        # First selection
        model1 = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model1 == "anthropic/claude-haiku-4"

        # Second selection (pool exhausted, vendor limit hit)
        model2 = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=1,
            existing_selections=[model1],
        )
        assert model2 == "openrouter/auto"

    def test_chinese_model_dissent(self):
        """Verify Chinese-trained models can be included as dissent instruments."""
        pools = {
            CouncilRole.RED_TEAM: [
                "anthropic/claude-haiku-4",
                "qwen/qwen-2.5-72b-instruct",  # Chinese model
            ],
        }

        router = RoleSpecializedRouter(
            role_pools=pools,
            max_per_vendor=1,
        )

        # Should be able to select Qwen for RED_TEAM
        seen_models = set()
        for _ in range(20):  # Sample many times
            model = router.select_model(
                role=CouncilRole.RED_TEAM,
                loop=0,
                seat_index=0,
                existing_selections=[],
            )
            seen_models.add(model)

        assert "qwen/qwen-2.5-72b-instruct" in seen_models
        assert len(seen_models) >= 2

    def test_unmapped_role_fallback(self):
        """Test fallback for roles not in role_pools."""
        pools = {
            CouncilRole.RED_TEAM: ["anthropic/claude-haiku-4"],
        }

        router = RoleSpecializedRouter(role_pools=pools)

        # DOMAIN_EXPERT not in pools, should fall back
        model = router.select_model(
            role=CouncilRole.DOMAIN_EXPERT,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert model == "openrouter/auto"


class TestCostAwareRouter:
    """Tests for CostAwareRouter."""

    def test_role_based_difficulty(self):
        """Test that roles map to appropriate difficulty tiers."""
        router = CostAwareRouter()

        # RED_TEAM should get cheap model (EASY -> T0)
        red_team_model = router.select_model(
            role=CouncilRole.RED_TEAM,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert red_team_model in CostAwareRouter.TIER_POOLS["T0"]

        # SYNTHESIZER should get premium model (HARD -> T2)
        synth_model = router.select_model(
            role=CouncilRole.SYNTHESIZER,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert synth_model in CostAwareRouter.TIER_POOLS["T2"]

        # DOMAIN_EXPERT should get mid-tier (MEDIUM -> T1)
        expert_model = router.select_model(
            role=CouncilRole.DOMAIN_EXPERT,
            loop=0,
            seat_index=0,
            existing_selections=[],
        )
        assert expert_model in CostAwareRouter.TIER_POOLS["T1"]


class TestEngineConfigValidation:
    """Tests for EngineConfig routing validation."""

    def test_custom_mode_requires_router(self):
        """Test that CUSTOM mode requires custom_router."""
        import os

        # Set API key for validation
        os.environ["OPENROUTER_KEY"] = "test-key"

        with pytest.raises(ValueError, match="custom_router required"):
            EngineConfig(routing_mode=RoutingMode.CUSTOM)

        # Cleanup
        del os.environ["OPENROUTER_KEY"]

    def test_custom_mode_with_router(self):
        """Test that CUSTOM mode works with custom_router provided."""
        import os

        os.environ["OPENROUTER_KEY"] = "test-key"

        router = PoolRouter(model_pool=["anthropic/claude-opus-4"])
        config = EngineConfig(
            routing_mode=RoutingMode.CUSTOM,
            custom_router=router,
        )

        assert config.routing_mode == RoutingMode.CUSTOM
        assert config.custom_router is router

        del os.environ["OPENROUTER_KEY"]

    def test_auto_mode_no_router_required(self):
        """Test that AUTO mode doesn't require custom_router."""
        import os

        os.environ["OPENROUTER_KEY"] = "test-key"

        config = EngineConfig(routing_mode=RoutingMode.AUTO)

        assert config.routing_mode == RoutingMode.AUTO
        assert config.custom_router is None

        del os.environ["OPENROUTER_KEY"]
