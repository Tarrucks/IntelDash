"""OSINT Framework taxonomy tree models.

The upstream ``lockfale/OSINT-Framework`` repo serves a single
``arf.json`` mind-map file with nested ``children`` arrays. We flatten
the taxonomy into a typed tree of folders + leaf URLs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class OsintLeaf(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: Literal["url"] = "url"
    url: str
    tags: list[str] = []


class OsintNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: Literal["folder"] = "folder"
    children: list[OsintNode | OsintLeaf] = []


OsintNode.model_rebuild()
