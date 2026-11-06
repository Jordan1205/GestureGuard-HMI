"""Context permissions used before GestureGuard previews an action."""

from .simulation import Factory


class CommandRouter:
    def __init__(self, factory: Factory) -> None:
        self.factory = factory

    def authorize(self, action: str, station_id: str) -> tuple[bool, str]:
        try:
            station = self.factory.station(station_id)
        except ValueError as error:
            return False, str(error)
        if action == "start" and station.state == "running":
            return False, f"{station.name} is already running; start is not permitted."
        if action == "pause" and station.state != "running":
            return False, f"{station.name} is {station.state}; pause requires a running station."
        if action not in {"start", "pause", "stop"}:
            return False, f"Unsupported command: {action}"
        return True, "Command is permitted in the current station state."

    def execute(self, action: str, station_id: str) -> tuple[bool, str]:
        return self.factory.command(action, station_id)
