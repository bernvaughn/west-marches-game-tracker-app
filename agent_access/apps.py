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
        reg("more", "Agent access", "agent_access:index", None, 90)
        reg("gm", "Agent connections", "agent_access:connections", is_gm, 50)
        reg("gm", "Agent batches", "agent_access:batches", is_gm, 40)
        reg("gm", "Proposed items", "agent_access:proposed_items", is_gm_or_admin, 30)
