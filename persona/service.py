from typing import List
from backend.leads.models import Lead
from backend.persona.models import Persona

def check_persona_match(lead: Lead, personas: List[Persona]) -> bool:
    # Simplified logic: 
    # if (title.includes("manager") && company_size > 50) { match = true; }
    # We will check if ANY rules match.
    # We assume 'rules_json' has structure like {"title_keyword": "manager", "min_company_size": 50}
    
    for persona in personas:
        rules = persona.rules_json
        match = True
        
        # Check Title
        if "title_keyword" in rules:
            if not lead.title or rules["title_keyword"].lower() not in lead.title.lower():
                match = False
        
        # Check Company Size
        if "min_company_size" in rules:
            # Parse lead size "50-200" -> 50 approx
            size_val = 0
            if lead.company_size:
                try:
                    parts = lead.company_size.split("-")
                    size_val = int(parts[0])
                except:
                    pass
            if size_val < rules["min_company_size"]:
                match = False
                
        if match:
            return True
            
    return False
