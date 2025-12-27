"""Built-in router implementations for Crucible."""

from crucible.routing.cost_aware import CostAwareRouter
from crucible.routing.defaults import CHINESE_DISSENT_MODELS, DEFAULT_ROLE_POOLS
from crucible.routing.diversity import DiversityRouter
from crucible.routing.pool import PoolRouter
from crucible.routing.role_mapped import RoleMappedRouter
from crucible.routing.role_specialized import RoleSpecializedRouter
from crucible.routing.tiered import TieredRouter

__all__ = [
    "PoolRouter",
    "DiversityRouter",
    "RoleMappedRouter",
    "TieredRouter",
    "RoleSpecializedRouter",
    "CostAwareRouter",
    "DEFAULT_ROLE_POOLS",
    "CHINESE_DISSENT_MODELS",
]
