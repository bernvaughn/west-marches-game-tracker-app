from django.apps import AppConfig


class AgentAccessConfig(AppConfig):
    name = "agent_access"

    def ready(self):
        from accounts import approvals

        from .approvals import pending_batches, pending_proposed_items

        approvals.register(pending_batches)
        approvals.register(pending_proposed_items)
