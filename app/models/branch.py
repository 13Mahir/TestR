"""
This file re-exports School and Branch from models/user.py.
They are co-located because Branch depends on School and both are small tables.
"""
from models.user import School, Branch

__all__ = ["School", "Branch"]
