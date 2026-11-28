from django.apps import AppConfig


class AgentAccessConfig(AppConfig):
    name = "agent_access"

    def ready(self):
        from accounts import approvals

        from .approvals import pending_batches, pending_proposed_items

        approvals.register(pending_batches)
        approvals.register(pending_proposed_items)

        from accounts import navigation
        from accounts.apps import is_gm, is_gm_or_admin

        reg = navigation.register
        reg("agent", "Agent access", "agent_access:index", is_gm_or_admin, 10, icon="person-gear")
        reg("agent", "Agent connections", "agent_access:connections", is_gm, 20, icon="link-45deg")
        reg("agent", "Agent batches", "agent_access:batches", is_gm, 30, icon="boxes")
        reg(
            "items",
            "Proposed items",
            "agent_access:proposed_items",
            is_gm_or_admin,
            40,
            icon="lightbulb",
        )
