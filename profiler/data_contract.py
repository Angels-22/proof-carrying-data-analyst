"""
Data Contract abstraction for VerifyAI (Phase 3.4).
Defines authoritative schemas, semantic definitions, metric glossaries,
and units preventing LLMs from hallucinating metric semantics.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SemanticMetric(BaseModel):
    name: str
    definition: str
    units: Optional[str] = None
    currency: Optional[str] = None
    is_authoritative: bool = True


class DatasetContract(BaseModel):
    dataset_name: str
    description: str
    column_types: Dict[str, str] = Field(default_factory=dict)
    semantic_glossary: Dict[str, SemanticMetric] = Field(default_factory=dict)
    date_columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)
    currency: str = "UNKNOWN"
    is_authoritative: bool = True


class DataContractRegistry:
    """Registry of authoritative dataset contracts."""

    _contracts: Dict[str, DatasetContract] = {}

    @classmethod
    def register_default_contracts(cls):
        # 1. Clean Sales Contract
        cls._contracts["sales.csv"] = DatasetContract(
            dataset_name="sales.csv",
            description="Authoritative transactional sales records.",
            column_types={
                "order_id": "string",
                "date": "datetime",
                "product_id": "string",
                "quantity": "integer",
                "unit_price": "float",
                "revenue": "float",
                "region": "string",
                "currency": "string",
            },
            semantic_glossary={
                "revenue": SemanticMetric(
                    name="revenue",
                    definition="Recognized gross sales revenue (quantity * unit_price), excluding tax.",
                    currency="USD",
                ),
                "quantity": SemanticMetric(
                    name="quantity",
                    definition="Number of physical units sold per order line.",
                    units="units",
                ),
            },
            date_columns=["date"],
            numeric_columns=["revenue", "quantity", "unit_price"],
            currency="USD",
        )

        # 2. Products Contract
        cls._contracts["products.csv"] = DatasetContract(
            dataset_name="products.csv",
            description="Authoritative product catalog mapping product_id to category and name.",
            column_types={
                "product_id": "string",
                "product_name": "string",
                "category": "string",
                "base_price": "float",
            },
            semantic_glossary={
                "category": SemanticMetric(
                    name="category",
                    definition="Product department category (e.g., Electronics, Footwear, Apparel).",
                )
            },
            date_columns=[],
            numeric_columns=["base_price"],
            currency="USD",
        )

    @classmethod
    def get_contract(cls, dataset_name: str) -> Optional[DatasetContract]:
        if not cls._contracts:
            cls.register_default_contracts()
        return cls._contracts.get(dataset_name)


# Initialize default contracts
DataContractRegistry.register_default_contracts()
