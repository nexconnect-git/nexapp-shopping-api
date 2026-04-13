class BaseAction:
    """Base class for executing business logic transactions."""
    
    def execute(self, *args, **kwargs):
        raise NotImplementedError("Actions must implement the execute method.")
