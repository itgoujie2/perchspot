"""
Skills package - Independent analysis skills for different property aspects
"""
from app.services.agent.skills.base_skill import BaseSkill
from app.services.agent.skills.property_skill import PropertySkill
from app.services.agent.skills.school_skill import SchoolSkill
from app.services.agent.skills.location_skill import LocationSkill
from app.services.agent.skills.investment_skill import InvestmentSkill

__all__ = [
    'BaseSkill',
    'PropertySkill',
    'SchoolSkill',
    'LocationSkill',
    'InvestmentSkill'
]
