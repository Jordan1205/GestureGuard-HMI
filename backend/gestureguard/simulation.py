"""A deterministic factory model; all measurements are simulated.

Counters derive from accumulated running time, rather than random values or
frontend animation frames. A fixed inspection pattern makes replay comparable.
"""

from dataclasses import asdict, dataclass
import math


@dataclass(slots=True)
class Station:
    id: str
    name: str
    state: str = "stopped"
    target_speed: float = 65.0
    rpm: float = 0.0
    airflow: float = 0.0
    throughput: float = 0.0
    items: int = 0
    passed: int = 0
    failed: int = 0
    progress: float = 0.0
    work: float = 0.0

    def snapshot(self) -> dict:
        result = asdict(self)
        result.pop("work")
        for key in ("rpm", "airflow", "throughput", "progress"):
            result[key] = round(result[key], 3)
        return result


class Factory:
    def __init__(self) -> None:
        self.selected = 0
        self.stations = [Station("ventilation", "Ventilation System"), Station("conveyor", "Conveyor System"), Station("inspection", "Inspection Station")]

    def station(self, station_id: str | None = None) -> Station:
        if station_id is None:
            return self.stations[self.selected]
        for station in self.stations:
            if station.id == station_id:
                return station
        raise ValueError(f"Unknown workstation: {station_id}")

    def select(self, index: int) -> None:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.stations):
            raise ValueError("Station index must be 0, 1, or 2.")
        self.selected = index

    def command(self, action: str, station_id: str | None = None) -> tuple[bool, str]:
        try:
            station = self.station(station_id)
        except ValueError as error:
            return False, str(error)
        if action == "start":
            if station.state == "running":
                return False, f"{station.name} is already running."
            station.state = "running"
        elif action == "pause":
            if station.state != "running":
                return False, f"{station.name} must be running before it can be paused."
            station.state = "paused"
        elif action == "stop":
            station.state = "stopped"
        else:
            return False, f"Unsupported simulated command: {action}"
        self.tick(0)
        return True, f"{station.name}: {action} executed."

    def set_speed(self, value: float, station_id: str | None = None) -> None:
        if not math.isfinite(value) or not 10 <= value <= 100:
            raise ValueError("Target speed must be between 10 and 100 percent.")
        self.station(station_id).target_speed = float(value)
        self.tick(0)

    def tick(self, dt: float) -> None:
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Simulation time must be finite and nonnegative.")
        for station in self.stations:
            running = station.state == "running"
            fraction = station.target_speed / 100
            station.rpm = round(1800 * fraction, 3) if running and station.id == "ventilation" else 0.0
            station.airflow = round(2.4 * fraction, 3) if running and station.id == "ventilation" else 0.0
            station.throughput = round(36 * fraction, 3) if running and station.id == "conveyor" else 0.0
            if running:
                rate = (0.6 if station.id == "conveyor" else 0.4) * fraction
                station.work += dt * rate
                completed = math.floor(station.work + 1e-9)
                if station.id == "inspection":
                    station.items = completed
                    station.failed = completed // 7
                    station.passed = completed - station.failed
                elif station.id == "conveyor":
                    station.items = completed
                station.progress = station.work % 1

    def reset(self) -> None:
        self.__init__()

    def snapshot(self) -> list[dict]:
        return [station.snapshot() for station in self.stations]
