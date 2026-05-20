"""BarentsWatch Historic AIS response models.

Per the developer portal, the ``/v1/historic/tracks/...`` family returns
a GeoJSON ``FeatureCollection``. Each feature is typically a LineString
of the vessel's path with timestamps in properties.

We type the envelope generically — GeoJSON FeatureCollection — and let
the geometry stay loose (``dict``) so we can pass through LineStrings,
MultiLineStrings, or Points without reshaping.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeoJSONFeature(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "Feature"
    geometry: dict
    properties: dict = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "FeatureCollection"
    features: list[GeoJSONFeature] = Field(default_factory=list)
