from typing import (
    Any,
    Iterable,
    Dict,
    List,
    Type,
    TypeVar,
    Union,
)
from dataclasses import asdict, is_dataclass
from enum import Enum
import dacite

from pcs.common import types


PrimitiveType = Union[str, int, float, bool, None]
DtoPayload = Dict[str, "SerializableType"]  # type: ignore
SerializableType = Union[  # type: ignore
    PrimitiveType,
    DtoPayload,  # type: ignore
    Iterable["SerializableType"],  # type: ignore
]

T = TypeVar("T")


class DataTransferObject:
    pass


def to_dict(obj: DataTransferObject) -> DtoPayload:
    if not is_dataclass(obj):
        AssertionError()
    return asdict(obj)


DtoType = TypeVar("DtoType", bound=DataTransferObject)


def from_dict_unconfigured(
    cls: Type[DtoType], data: DtoPayload, cast_config: List[Type[Enum]],
) -> DtoType:
    return dacite.from_dict(
        data_class=cls,
        data=data,
        # NOTE: all enum types has to be listed here in key cast
        # see: https://github.com/konradhalas/dacite#casting
        config=dacite.Config(
            cast=[
                types.CibNvsetType,
                types.CibRuleInEffectStatus,
                types.CibRuleExpressionType,
                types.CorosyncTransportType,
                types.DrRole,
                types.ResourceRelationType,
            ]
        ),
    )


def from_dict(cls: Type[DtoType], data: DtoPayload) -> DtoType:
    cast_config: List[Type[Enum]] = [
        types.CibNvsetType,
        types.CibRuleExpressionType,
        types.DrRole,
        types.ResourceRelationType,
    ]
    return from_dict_unconfigured(cls, data, cast_config)


class ImplementsToDto:
    def to_dto(self) -> Any:
        raise NotImplementedError()


class ImplementsFromDto:
    @classmethod
    def from_dto(cls: Type[T], dto_obj: Any) -> T:
        raise NotImplementedError()
