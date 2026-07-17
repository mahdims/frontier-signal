from abc import ABC, abstractmethod
from frontier_signal.schemas import RawItem, SourceConfig


class Collector(ABC):
    @abstractmethod
    def collect(self, source: SourceConfig) -> list[RawItem]:
        raise NotImplementedError
