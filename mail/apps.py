import pkgutil
from importlib import import_module

from django.apps import AppConfig


class MailConfig(AppConfig):
    name = "mail"
    label = "mail"
    verbose_name = "Mail"

    def ready(self):
        # Auto-discover and register hooks_* modules
        for module_info in pkgutil.iter_modules([self.path]):
            if module_info.name.startswith("hooks_"):
                try:
                    module = import_module(f"mail.{module_info.name}")
                    if hasattr(module, "register"):
                        module.register()
                except ImportError as e:
                    if e.name == f"mail.{module_info.name}":
                        raise
                    # Re-raise any other import error
                    raise


def discover(prefix: str):
    """Discover and import all modules matching the given prefix.

    Returns a list of imported module objects.
    """
    import mail
    modules = []
    for module_info in pkgutil.iter_modules(mail.__path__):
        if module_info.name.startswith(prefix):
            module = import_module(f"mail.{module_info.name}")
            modules.append(module)
    return modules